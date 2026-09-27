---
name: login-with-playwright
description: When needing to login to URLS4IRL, or go to the homepage, then we need to do these tasks.
---

The website is available for development at http://127.0.0.1:8659/.

Precondition: the stack must be up with `make up p=ui d=1` (dev, Vite dev server) or `make up-built d=1` (pre-built assets). On the default `make up d=1` stack there is no `vite`, so pages render unstyled.

If needing to login, the username may be passed in as **$0**.

Otherwise, use: u4i_test1

The password is always in the following format:

**username**@urls4irl.app

For example, you can use u4i_test1@urls4irl.app as the password for user with username u4i_test1.
