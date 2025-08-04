from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text
from database import Base
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    email = Column(String, unique=True)


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    ad_id = Column(Integer, ForeignKey("ads.id", ondelete="CASCADE"), index=True)
    sender_username = Column(String, index=True)
    text = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

    ad = relationship("Ad", back_populates="messages")

class Ad(Base):
    __tablename__ = "ads"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(String)
    price = Column(Float)
    category = Column(String)
    photo_filename = Column(String)
    owner_username = Column(String)
    messages = relationship("Message", back_populates="ad", cascade="delete")


owner_username = Column(String, ForeignKey("users.username"))
