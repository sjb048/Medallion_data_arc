from .base import download_file, HAS_PANDAS
import xml.etree.ElementTree as ET
import pandas as pd

def parse_xml(url:str, filepath:str)->tuple:
    download_file(url, filepath)
    records=[]
    try:
        tree=ET.parse(filepath)
        root=tree.getroot()
        for child in root:
            record={}
            if len(child)>0:
                for subchild in child:
                    tag=subchild.tag.split('}')[-1] if '}' in subchild.tag else subchild.tag
                    record[tag]=subchild.text
            else:
                record=dict(child.attrib)
                if child.text and child.text.strip():
                    tag=child.tag.split('}')[-1] if '}' in child.tag else child.tag
                    record[tag]=child.text.strip()
            if record: records.append(record)
        if not records and HAS_PANDAS:
            try: df=pd.read_xml(filepath); records=df.to_dict('records')
            except: pass
    except Exception as e:
        print(f"XML parse error: {e}")
    return records, filepath
