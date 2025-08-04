from sqlalchemy import Column, Integer, String, Float, ForeignKey
from database import Base


# models.py
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    email = Column(String, unique=True)


class Ad(Base):
    __tablename__ = "ads"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(String)
    price = Column(Float)
    category = Column(String)
    photo_filename = Column(String)
    owner_username = Column(String)

owner_username = Column(String, ForeignKey("users.username"))