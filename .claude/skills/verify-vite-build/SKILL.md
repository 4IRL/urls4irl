# Verify Build
1. Run `docker compose exec vite npx vite build` and check for errors
2. If errors found, fix import paths, named/default export mismatches, and syntax issues
3. Re-run build until clean
4. Check for any temporary debug code (window.* hacks, console.logs) and remove them
5. Report summary of what was fixed
