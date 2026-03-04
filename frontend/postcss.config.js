// Placed in frontend/ (not project root) because postcss-load-config traverses
// upward from the CSS file's directory; CSS files in frontend/styles/ will find this config.
export default {
  plugins: {
    "postcss-preset-env": {
      stage: 2,
      features: {
        // Disable custom-properties polyfill — the app uses CSS custom properties
        // extensively and relies on runtime JS setProperty(). Inlining them would
        // break the cascade and runtime theme changes.
        "custom-properties": false,
      },
    },
    autoprefixer: {},
  },
};
