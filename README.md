# URLS4IRL

[![CI and Tests](https://github.com/4IRL/urls4irl/actions/workflows/CI.yml/badge.svg?branch=dev)](https://github.com/4IRL/urls4irl/actions/workflows/CI.yml)

## Share URLs With People You Know!

Ever shared a link with someone and then tried to search through your chat history to find it again?

URLS4IRL was born with the idea to be able to easily share URLs with friends or coworkers.

It allows each user to create one or many UTubs (URL Tubs) where they can:

- Add/remove URLs
- Add/remove other users to each UTub
- Add tags to each URL
- Add descriptions to each UTub

It is built on Flask, and uses a PostgreSQL database. The frontend is built using jQuery, with HTML/CSS,
and integrates Bootstrap for responsiveness.

This is our first web app and we are exciting to share it with the world! Come watch us grow!

###### tags: `URLs`, `Flask`, `Python`, `HTML`, `CSS`, `Javascript`, `PostgreSQL`

## :memo: Progress

### Step 1: Get the Product :arrow_right: IRL :arrow_left: (Into Real Life)!

- [x] Add login/logout/session capability
- [x] Add UTub and user-specific UTub capability
- [x] Add URL and UTub specific URL capability
- [x] Add tags adding capability
- [x] Give correct permissions to correct users for:
  - [x] Ability to see a UTub if added to another user's
  - [x] Ability to delete a UTub if the owner
  - [x] Ability add a URL to any UTub user is a part of
  - [x] Ability to delete any URL in the UTub if the owner of the UTub
  - [x] Ability for current user to delete a URL in another user's UTub if that current user added it
  - [x] Ability to add tags to any URL
  - [x] Ability for the UTub owner to remove tags on any URL in their UTub
  - [x] Ability for a user to leave a UTub
  - [x] Ability for a UTub creator to remove a user in their UTub (besides themselves)
- [x] User home page with their UTubs displayed, including:
  - [x] All URLs shown for all selected UTubs, separated per UTub
  - [x] All tags shown for all selected UTubs
- [x] Splash page for guests/users who aren't logged in
- [x] Error pages
- [x] Provide mock data through the Flask CLI
- [x] Write integration tests for backend + database
  - [x] Run tests using GitHub Actions
  - [x] Enforce tests as gate before a PR is approved
  - [x] Distribute tests among multiple GitHub workers
- [ ] Write functional tests for the frontend UI

:rocket:

### Step 2: Goals for Publicity

How about we add some goals we need to hit before we can go fully public?

- [x] Email confirmation
- [x] URL commonizer to avoid messy URL savings
  > (i.e. www.google.com vs google.com, these should be the same regardless of what the user typed in)
- [x] Hosting the website somewhere
- [ ] [Finish this Readme!](https://hackmd.io/2uvlNeFrT-qBu3qiXTcC6w?both)

### Step 3: Reach Goals

> Let's get some reach goals, shall we?

- [ ] User settings page
- [ ] RestAPI developed for the backend
- [ ] Android app developed from the RestAPI

---

### **Setting Up Migrations**

**FLASK_ENV** environment variable must be set to run while in the main directory.

```
set FLASK_ENV=run
flask db init
```

Now the migrations folder is setup.

---

### **Running Tests**

From this directory, run the following command:

```
pytest
```

This will print out a log as well as whether or not tests passed.

All tests are included in the _tests_ directory

---

### **Mock Data and Database Management with the CLI**

From this directory, with the virtual environment enabled, the following commands are enabled:

```
`flask addmock users`                       Adds 5 mock users with their emails validated
`flask addmock utubs`                       Adds 5 UTubs, this can be repeated to create multiple duplicate UTubs with same name. Runs users command first.
`flask addmock utubs --no-dupes`            Creates 5 UTubs but won't if UTub with name already exists. Runs users command first.
`flask addmock utubmembers`                 Adds all users to all UTubs, even duplicates. Runs utubs commmand first.
`flask addmock utubmembers --no-dupes`      Adds all users to all UTubs, even duplicates. Does not create duplicate UTubs.
`flask addmock url foo bar baz`             Adds "foo", "bar", and "baz" as URLs to all UTubs, runs utubmembers command first
`flask addmock url --no-dupes foo bar baz`  Adds "foo", "bar", and "baz" as URLs to all UTubs, runs utubmembers command first. Does not create duplicate UTubs.
`flask addmock urls`                        Adds 5 URLs to all UTubs, runs utubmembers command first
`flask addmock urls --no-dupes`             Adds 5 URLs to all UTubs, without creating duplicate UTubs.
`flask addmock tags`                        Adds 5 tags to each URL in each UTub, runs urls command first. 
`flask addmock tags --no-dupes`             Adds 5 tags to each URL in each UTub, without creating duplicate UTubs.
`flask addmock all`                         Equivalent to `flask addmock tags`
`flask addmock all --no-dupes`              Equivalent to `flask addmock tags --no-dupes`
`flask managedb clear [test|dev]`           Clears each table, can specify either test or dev database
`flask managedb drop [test|dev]`            Drops all tables in the datbase, can specify either test or dev database
```

Note that some of these commands assume a predefined set of environment variables defining the database URI for either test or development.

Follow any commend with command with `--help` to see a list of options for that given command.

For example:

```
`flask addmock --help`
`flask managedb --help`
`flask addmock utubs --help`
```
