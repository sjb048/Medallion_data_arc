from pymongo import MongoClient
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.development')

MONGODB_USER = os.getenv('MONGODB_USER')
MONGODB_PASSWORD = os.getenv('MONGODB_PASSWORD')
MONGODB_AUTHDB = os.getenv('MONGODB_AUTHDB', 'your_auth_db_name')  # Replace with your default auth db name
MONGODB_HOST = os.getenv('MONGODB_HOST', 'localhost')
MONGODB_PORT = int(os.getenv('MONGODB_PORT', 'your_port_number'))  # Replace with your default port number
MONGODB_DB = os.getenv('MONGODB_DASHBOARD_DATABASE', 'your_database_name')

def connect_to_db(
        db_name=None,
        username=None,
        password=None,
        host=None,
        port=None,
        auth_source=None,
        connection_uri=None
        ):
    """Connect to MongoDB database."""
    try:

        db_name = db_name or MONGODB_DB
        username = username or MONGODB_USER
        password = password or MONGODB_PASSWORD
        host = host or MONGODB_HOST
        port = port or MONGODB_PORT
        auth_source = auth_source or MONGODB_AUTHDB
        
        if connection_uri:
            # Use provided URI
            uri = connection_uri
        elif username and password:
            # Build URI with authentication
            uri = f"mongodb://{username}:{password}@{host}:{port}/{db_name}?authSource={auth_source}"
        else:
            # Build URI without authentication
            uri = f"mongodb://{host}:{port}/{db_name}"

        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        db = client[db_name]
        # Test connection
        client.admin.command('ping')
        print(f"✓ Successfully connected to database: {db_name}")
        return db
 
    except Exception as e:
        print(f"✗ Connection failed: {type(e).__name__}: {str(e)}")
        return None 
    

