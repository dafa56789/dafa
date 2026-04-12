from sqlalchemy import create_engine, Column, Integer, Text
from sqlalchemy.orm import declarative_base, sessionmaker

engine = create_engine("sqlite:///memory.db")
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()

class Memory(Base):
    __tablename__ = "memories"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    content = Column(Text)

def init_db():
    Base.metadata.create_all(bind=engine)
