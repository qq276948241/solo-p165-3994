import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///gym.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_COURSE_CAPACITY = 12
    CANCELLATION_WINDOW_HOURS = 2
