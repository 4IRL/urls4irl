from os import environ

from dotenv import load_dotenv

from src import create_app

load_dotenv(override=True)

is_production_env_var = environ.get("PRODUCTION", default="false")
use_local_js_bundles_var = environ.get("USE_LOCAL_BUNDLES", default="false")

if is_production_env_var.lower() not in ("false", "true"):
    print("Invalid/missing PRODUCTION environment variable.")
    quit()

is_production: bool = is_production_env_var.lower() == "true"
use_local_js_bundles: bool = use_local_js_bundles_var.lower() == "true"

app = create_app(production=is_production, use_local_js_bundles=use_local_js_bundles)

if __name__ == "__main__":
    if not is_production:
        print("Not in production.")
        app.run(
            host=environ.get("HOST", default=None),
            port=environ.get("PORT", default="5000"),
        )
    else:
        print("In production.")
        app.run(host="0.0.0.0")
