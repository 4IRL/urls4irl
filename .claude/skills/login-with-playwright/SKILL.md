---
name: login-with-playwright
description: When needing to login to URLS4IRL, or go to the homepage, then we need to do these tasks.
---

The website is available for development at http://127.0.0.1:8659/ in the primary clone. In a git worktree the port differs: use the web URL printed by `make stack-info` (run in that checkout). Each checkout has its own session cookie, so logging into one never logs out another.

Precondition: the stack must be up with `make up p=ui d=1` (dev, Vite dev server) or `make up-built d=1` (pre-built assets). On the default `make up d=1` stack there is no `vite`, so pages render unstyled.

A fresh worktree's dev DB (`u4i_dev_<slug>`) is created empty: run `make addmock` (or `make reset-db`) once in that checkout so the seeded `u4i_test1`/`u4i_test2` logins exist.

If needing to login, the username may be passed in as **$0**.

Otherwise, use: u4i_test1

The password is always in the following format:

**username**@urls4irl.app

For example, you can use u4i_test1@urls4irl.app as the password for user with username u4i_test1.
