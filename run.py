from urls4irl import create_app
from os import environ
from dotenv import load_dotenv
from urls4irl.config import TestingConfig

load_dotenv(override=True)

if environ.get('TESTING') is not None and environ.get('TESTING').lower() == 'true':
    print("In testing")
    app = create_app(TestingConfig, True)
else:
    print("Not in testing")
    app = create_app()

if __name__ == "__main__":
    app.run(port=5001)
    