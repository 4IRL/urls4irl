from os import environ

from dotenv import load_dotenv

from src import create_app

load_dotenv(override=True)
if environ.get("PRODUCTION") is None:
    print("Missing PRODUCTION environment variable.")
    quit()

is_production_env_var = environ.get("PRODUCTION")
use_local_js_bundles_var = environ.get("USE_LOCAL_BUNDLES", default="false")

if is_production_env_var.lower() not in ("false", "true"):
    print("Invalid PRODUCTION environment variable.")
    quit()
else:
    is_production = True if is_production_env_var.lower() == "true" else False

use_local_js_bundles = True if use_local_js_bundles_var.lower() == "true" else False

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
