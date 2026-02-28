from sqlalchemy import create_engine, text
from config import DB_CONFIG

def get_engine():
    url=f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
    engine = create_engine(url)
    return engine

if __name__ == "__main__":
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print("Conexion exitosa a la base de datos", result.scalar())
    