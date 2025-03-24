import glob
import os
import re

from flask import Flask
from flask_assets import Bundle, Environment
from webassets.filter import Filter, register_filter


class StrictModeFilter(Filter):
    name = "remove_strict_mode"

    def output(self, _in, out, **kwargs):
        content = _in.read()
        pattern = re.compile(r'[\'"]use strict[\'"]\s*;?\s*', re.MULTILINE)
        cleaned_content = pattern.sub("", content)
        out.write('"use strict";')
        out.write(cleaned_content)


def prepare_bundler_for_js_files(
    abs_js_path: str,
    relative_js_path: str,
    app: Flask,
    assets: Environment,
    assets_url_prefix: str | None,
    is_testing_or_prod: bool,
):
    """
    Bundles the JS files into a single file `logged_in.js`, stored in the `gen` directory.
    A blueprint method under `assets` is used to properly route clients to retrieve this file.
    For testing or production, the file needs to be only bundled and served once, so the build is
    forced on application build.
    For development, we'd like to hot reload based on file changes to the unbundled JS files.

    args:
        abs_js_path (str): The absolute path to search for the javascript files
        rel_js_path (str): The relative (to the Flask app) path to search for the javascript files
        app (Flask): The current Flask application
        assets (Environment): The Flask-Assets environment to bundle the JS files
        assets_url_prefix (str | None): The Blueprint URL prefix serving the JS file
        is_testing_or_prod (bool): Whether this is testing/production, or development
    """
    BUNDLED_JS_FILE = "logged_in.js"

    logged_in_js_files = glob.glob(abs_js_path, recursive=True)

    assets.init_app(app)
    app.config["ASSETS_CACHE"] = False
    app.config["ASSETS_MANIFEST"] = False
    app.config["ASSETS_DEST"] = os.path.join(app.root_path, "gen")

    register_filter(StrictModeFilter)
    logged_in_js = Bundle(
        *logged_in_js_files,
        depends=relative_js_path,
        filters=[
            "jsmin",
            "remove_strict_mode",
        ],
        output=BUNDLED_JS_FILE,
    )

    with app.app_context():
        assets.directory = os.path.join(app.root_path, "gen")
        assets.auto_build = not is_testing_or_prod
        assets.url = assets_url_prefix
        assets.register("logged_in_js", logged_in_js)
        if is_testing_or_prod:
            logged_in_js.build(force=True)
