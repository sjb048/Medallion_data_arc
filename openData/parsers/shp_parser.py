# shp_parser.py
# Shapefile parser - converts .shp and zipped shapefiles to JSON/GeoJSON

import os
import zipfile
import tempfile
import shutil
import numpy as np
from .base import download_file, normalize_col, HAS_GEOPANDAS

if HAS_GEOPANDAS:
    import geopandas as gpd


def sanitize_value(val):
    """Sanitize values for JSON serialization"""
    if val is None:
        return None
    if hasattr(val, "item"):  # numpy types
        val = val.item()
    if isinstance(val, float) and (val != val):  # NaN check
        return None
    return val


def list_all_files(directory: str) -> list:
    """List all files in directory recursively"""
    all_files = []
    for root, dirs, files in os.walk(directory):
        # Skip Mac OS X metadata folders
        if '__MACOSX' in root:
            continue
        for f in files:
            rel_path = os.path.relpath(os.path.join(root, f), directory)
            all_files.append(rel_path)
    return all_files


def find_geospatial_file(directory: str) -> tuple:
    """
    Find any geospatial file in directory.
    Returns (filepath, format) or (None, None)
    
    Checks for: .shp, .geojson, .json, .gpkg, .gdb, .kml
    """
    # Priority order for geospatial formats
    format_checks = [
        ('.shp', 'shapefile'),
        ('.geojson', 'geojson'),
        ('.gpkg', 'geopackage'),
        ('.kml', 'kml'),
        ('.gml', 'gml'),
    ]
    
    all_files = []
    
    for root, dirs, files in os.walk(directory):
        # Skip Mac OS X metadata
        if '__MACOSX' in root:
            continue
        
        # Check for file geodatabase (folder ending in .gdb)
        for d in dirs:
            if d.lower().endswith('.gdb'):
                return os.path.join(root, d), 'geodatabase'
        
        for f in files:
            full_path = os.path.join(root, f)
            f_lower = f.lower()
            all_files.append(f)
            
            for ext, fmt in format_checks:
                if f_lower.endswith(ext):
                    return full_path, fmt
            
            # Check for .json files that might be GeoJSON
            if f_lower.endswith('.json'):
                # Try to detect if it's GeoJSON by reading first few bytes
                try:
                    with open(full_path, 'r') as fp:
                        content = fp.read(500)
                        if '"type"' in content and ('"Feature"' in content or '"FeatureCollection"' in content):
                            return full_path, 'geojson'
                except:
                    pass
    
    return None, None


def parse_shp(url: str, filepath: str, to_crs: str = "EPSG:4326") -> tuple:
    """
    Download and parse a geospatial file to JSON records.
    
    Supports: Shapefile (.shp), GeoJSON, GeoPackage (.gpkg), 
              File Geodatabase (.gdb), KML, and ZIP archives containing any of these.
    
    Args:
        url: URL to download the file from
        filepath: Local path to save the file
        to_crs: Coordinate reference system to convert to (default WGS84)
        
    Returns:
        Tuple of (records list with geometry as GeoJSON, filepath)
    """
    download_file(url, filepath)
    records = []
    
    if not HAS_GEOPANDAS:
        print("       ⚠️ geopandas not installed")
        return [], filepath
    
    geo_path = None
    geo_format = None
    temp_dir = None
    gdf = None
    
    try:
        # First, try to read directly with geopandas (handles many formats automatically)
        try:
            print(f"       📖 Attempting direct read...")
            gdf = gpd.read_file(filepath)
            geo_format = "direct"
            print(f"       ✅ Direct read successful")
        except Exception as direct_error:
            # Direct read failed, check if it's a ZIP
            is_zip = False
            try:
                is_zip = zipfile.is_zipfile(filepath)
            except:
                pass
            
            if is_zip:
                # Extract and find geospatial file
                temp_dir = tempfile.mkdtemp(prefix="geo_extract_")
                print(f"       📦 Extracting ZIP archive...")
                
                with zipfile.ZipFile(filepath, 'r') as zf:
                    # List contents for debugging
                    contents = zf.namelist()
                    print(f"       📋 ZIP contains {len(contents)} items")
                    
                    # Show relevant files
                    geo_extensions = ['.shp', '.geojson', '.json', '.gpkg', '.gdb', '.kml', '.gml']
                    geo_files = [f for f in contents if any(f.lower().endswith(ext) for ext in geo_extensions)]
                    
                    if geo_files:
                        print(f"       📍 Geo files found: {geo_files[:5]}")
                    else:
                        # Show what IS in the zip
                        sample_files = [f for f in contents if not f.startswith('__MACOSX')][:10]
                        print(f"       📁 Sample contents: {sample_files}")
                    
                    zf.extractall(temp_dir)
                
                # Find geospatial file
                geo_path, geo_format = find_geospatial_file(temp_dir)
                
                if not geo_path:
                    print(f"       ❌ No supported geospatial file found in ZIP")
                    print(f"       💡 Supported: .shp, .geojson, .gpkg, .gdb, .kml, .gml")
                    
                    # Last resort: try reading the ZIP directly with geopandas
                    # (works for some formats like zipped GeoJSON)
                    try:
                        print(f"       🔄 Trying geopandas ZIP reader...")
                        gdf = gpd.read_file(f"zip://{filepath}")
                        geo_format = "zip_direct"
                        print(f"       ✅ ZIP direct read successful")
                    except Exception as zip_err:
                        print(f"       ❌ ZIP direct read failed: {zip_err}")
                        return [], filepath
                else:
                    print(f"       📍 Found {geo_format}: {os.path.basename(geo_path)}")
                    gdf = gpd.read_file(geo_path)
            else:
                # Not a ZIP, re-raise the original error
                print(f"       ❌ Cannot read file: {direct_error}")
                return [], filepath
        
        if gdf is None or len(gdf) == 0:
            print(f"       ⚠️ No features loaded")
            return [], filepath
            
        print(f"       📊 Loaded {len(gdf)} features, CRS: {gdf.crs}")
        
        # Convert CRS if needed
        if gdf.crs is not None and to_crs:
            try:
                gdf = gdf.to_crs(to_crs)
                print(f"       🔄 Converted to {to_crs}")
            except Exception as e:
                print(f"       ⚠️ CRS conversion failed: {e}")
        
        # Normalize column names
        gdf.columns = [normalize_col(col) if col != 'geometry' else col 
                       for col in gdf.columns]
        
        # Convert to records with GeoJSON geometry
        for idx, row in gdf.iterrows():
            record = {}
            for col in gdf.columns:
                if col == 'geometry':
                    if row.geometry is not None and not row.geometry.is_empty:
                        record['geometry'] = row.geometry.__geo_interface__
                        record['geometry_type'] = row.geometry.geom_type
                        try:
                            centroid = row.geometry.centroid
                            record['centroid_lat'] = sanitize_value(centroid.y)
                            record['centroid_lon'] = sanitize_value(centroid.x)
                        except:
                            pass
                    else:
                        record['geometry'] = None
                        record['geometry_type'] = None
                else:
                    record[col] = sanitize_value(row[col])
            
            records.append(record)
        
        print(f"       ✅ Parsed {geo_format or 'geospatial'} ({len(records)} features)")
        
    except Exception as e:
        print(f"       ❌ Geospatial parse failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up temp directory
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
    
    return records, filepath


def parse_shp_to_geojson(url: str, filepath: str, output_path: str = None, 
                         to_crs: str = "EPSG:4326") -> tuple:
    """
    Download and convert a geospatial file to a GeoJSON file.
    """
    download_file(url, filepath)
    
    if not HAS_GEOPANDAS:
        print("       ⚠️ geopandas not installed")
        return {}, filepath
    
    temp_dir = None
    
    try:
        # Try direct read first
        try:
            gdf = gpd.read_file(filepath)
        except:
            # Try as ZIP
            if zipfile.is_zipfile(filepath):
                temp_dir = tempfile.mkdtemp(prefix="geo_extract_")
                with zipfile.ZipFile(filepath, 'r') as zf:
                    zf.extractall(temp_dir)
                geo_path, _ = find_geospatial_file(temp_dir)
                if geo_path:
                    gdf = gpd.read_file(geo_path)
                else:
                    # Try zip:// protocol
                    gdf = gpd.read_file(f"zip://{filepath}")
            else:
                raise
        
        if gdf.crs is not None and to_crs:
            gdf = gdf.to_crs(to_crs)
        
        # Normalize column names
        gdf.columns = [normalize_col(col) if col != 'geometry' else col 
                       for col in gdf.columns]
        
        # Determine output path
        if output_path is None:
            base = os.path.splitext(filepath)[0]
            output_path = f"{base}.geojson"
        
        # Save as GeoJSON
        gdf.to_file(output_path, driver='GeoJSON')
        print(f"       ✅ Saved GeoJSON: {output_path}")
        
        # Also return as dict
        import json
        with open(output_path, 'r') as f:
            geojson_dict = json.load(f)
        
        return geojson_dict, output_path
        
    except Exception as e:
        print(f"       ❌ Conversion failed: {e}")
        return {}, filepath
    
    finally:
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except:
                pass


def parse_shp_from_file(filepath: str, to_crs: str = "EPSG:4326") -> list:
    """
    Parse a geospatial file that's already downloaded.
    """
    if not HAS_GEOPANDAS:
        print("⚠️ geopandas not installed")
        return []
    
    if not os.path.exists(filepath):
        print(f"❌ File not found: {filepath}")
        return []
    
    records = []
    temp_dir = None
    
    try:
        # Try direct read first
        try:
            gdf = gpd.read_file(filepath)
        except:
            if zipfile.is_zipfile(filepath):
                temp_dir = tempfile.mkdtemp(prefix="geo_extract_")
                with zipfile.ZipFile(filepath, 'r') as zf:
                    zf.extractall(temp_dir)
                geo_path, _ = find_geospatial_file(temp_dir)
                if geo_path:
                    gdf = gpd.read_file(geo_path)
                else:
                    gdf = gpd.read_file(f"zip://{filepath}")
            else:
                raise
        
        if gdf.crs is not None and to_crs:
            gdf = gdf.to_crs(to_crs)
        
        gdf.columns = [normalize_col(col) if col != 'geometry' else col 
                       for col in gdf.columns]
        
        for idx, row in gdf.iterrows():
            record = {}
            for col in gdf.columns:
                if col == 'geometry':
                    if row.geometry is not None and not row.geometry.is_empty:
                        record['geometry'] = row.geometry.__geo_interface__
                        record['geometry_type'] = row.geometry.geom_type
                        try:
                            centroid = row.geometry.centroid
                            record['centroid_lat'] = sanitize_value(centroid.y)
                            record['centroid_lon'] = sanitize_value(centroid.x)
                        except:
                            pass
                    else:
                        record['geometry'] = None
                else:
                    record[col] = sanitize_value(row[col])
            records.append(record)
        
        return records
        
    except Exception as e:
        print(f"❌ Geospatial parse failed: {e}")
        return []
    
    finally:
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except:
                pass