from urls4irl import create_app
from os import environ
from dotenv import load_dotenv
from urls4irl.config import TestingConfig

load_dotenv()

if environ.get('TESTING').lower() == 'true':
    app = create_app(TestingConfig)
else:
    app = create_app()

if __name__ == "__main__":
    app.run()