import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')

    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///lexoffice.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

    # JWT
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 900)))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(seconds=int(os.getenv('JWT_REFRESH_TOKEN_EXPIRES', 2592000)))
    JWT_TOKEN_LOCATION = ['cookies', 'headers']
    JWT_COOKIE_SECURE = False  # True in production
    JWT_COOKIE_CSRF_PROTECT = False  # WTF-CSRF handles form protection
    JWT_ACCESS_COOKIE_NAME = 'access_token'
    JWT_REFRESH_COOKIE_NAME = 'refresh_token'
    JWT_COOKIE_SAMESITE = 'Lax'

    # Mail
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME ='ibrahimfakhreyams@gmail.com'
    MAIL_PASSWORD = 'aqge lded enbk kgrz'
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'ibrahimfakhreyams@gmail.com')

    # File Upload
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'static', 'uploads'))
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_FILE_SIZE', 20971520))  # 20MB
    ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc', 'png', 'jpg', 'jpeg', 'xlsx', 'xls'}

    # SMS
    SMS_PROVIDER = os.getenv('SMS_PROVIDER', 'twilio')
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID', '')
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN', '')
    TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER', '')

    # Azure OpenAI
    AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT', '')
    AZURE_OPENAI_API_KEY = os.getenv('AZURE_OPENAI_API_KEY', '')
    AZURE_OPENAI_DEPLOYMENT = os.getenv('AZURE_OPENAI_DEPLOYMENT', '')
    AZURE_OPENAI_API_VERSION = os.getenv('AZURE_OPENAI_API_VERSION', '2024-02-15-preview')

    # Redis / Celery
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

    # App Settings
    DEFAULT_LANGUAGE = os.getenv('DEFAULT_LANGUAGE', 'ar')
    ITEMS_PER_PAGE = int(os.getenv('ITEMS_PER_PAGE', 20))
    OTP_EXPIRY_MINUTES = int(os.getenv('OTP_EXPIRY_MINUTES', 10))
    OTP_MAX_ATTEMPTS = int(os.getenv('OTP_MAX_ATTEMPTS', 3))
    LOGIN_MAX_ATTEMPTS = int(os.getenv('LOGIN_MAX_ATTEMPTS', 5))
    LOGIN_LOCKOUT_MINUTES = int(os.getenv('LOGIN_LOCKOUT_MINUTES', 15))

    # Rate Limiting
    RATELIMIT_STORAGE_URI = os.getenv('REDIS_URL', 'memory://')
    RATELIMIT_DEFAULT = '200/hour'


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///lexoffice.db')
    RATELIMIT_ENABLED = False  # Disable rate limiting in development


class ProductionConfig(Config):
    DEBUG = False
    JWT_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///test_lexoffice.db'
    WTF_CSRF_ENABLED = False
    JWT_COOKIE_CSRF_PROTECT = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig,
}
