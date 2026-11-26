from sqlalchemy import text

from app.database.session import engine

with engine.connect() as connection:
    print(connection.execute(text("SELECT version()")).scalar())
    print("DATABASE CONNECTION SUCCESSFUL")
