from src import create_app

app = create_app()
if __name__ == "__main__":
    if not app.config["PRODUCTION"]:
        print("Not in production.")
        app.run(host=app.config["FLASK_RUN_HOST"], port=app.config["FLASK_RUN_PORT"])
    else:
        print("In production.")
        app.run(host="0.0.0.0")
