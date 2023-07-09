from urls4irl import create_app
from os import environ
from dotenv import load_dotenv

load_dotenv(override=True)
if environ.get('PRODUCTION') is None:
    print("Missing PRODUCTION environment variable.")
    quit()

is_production = environ.get('PRODUCTION')
app = create_app()

if __name__ == "__main__":
    if is_production.lower() == 'false':
        print("Not in production.")
        app.run(port=5000)
    elif is_production.lower() == 'true':
        print("In production.")
        app.run(host='0.0.0.0')
    else:
        print("Invalid PRODUCTION environment variable.")
