from sqlalchemy import Date, Enum, ForeignKey, create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base
import datetime

# Database setup
Base = declarative_base()
engine = create_engine("sqlite:///users.db")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    first_name = Column(String, nullable=False)
    phone_number = Column(String, nullable=False)
    language = Column(Enum("am", "or", "en", "ar", name="language_enum"), nullable=False)
    donation_amount = Column(Integer, nullable=False)  
    duration = Column(Integer, nullable=False)
    last_payment_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Donation(Base):
    __tablename__ = "donations"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Integer, nullable=False) 
    date_paid = Column(Date, nullable=False)
    receipt = Column(String, nullable=True)  
    

Base.metadata.create_all(engine)