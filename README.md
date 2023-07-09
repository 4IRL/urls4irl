# URLS4IRL

## Share URLs With People You Know!

Ever shared a link with someone and then tried to search through your chat history to find it again?

URLS4IRL was born with the idea to be able to easily share URLs with friends or coworkers.

It allows each user to create one or many UTubs (URL Tubs) where they can:

- Add/remove URLs
- Add/remove other users
- Add tags to each URL
- Add descriptions to each UTub
- Chat with other users in their UTub

It is built on Flask, and uses a SQLite database with an eye towards migrating to a PostgreSQL
database in the future.

This is our first web app and we are exciting to share it with the world! Come watch us grow!

###### tags: `URLs`, `Flask`, `Python`, `HTML`, `CSS`, `Javascript`, `SQLite`, `PostgreSQL`

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
- [ ] User home page with their UTubs displayed, including:
  - [ ] All URLs shown for all selected UTubs, separated per UTub
  - [ ] All tags shown for all selected UTubs
  - [ ] Chat box for UTub specific chat, with drop down menu to choose which UTub specific chat is shown
- [ ] Splash page for guests/users who aren't logged in
- [ ] User settings page
- [ ] Error pages
- [ ] [A license!](https://gist.github.com/nicolasdao/a7adda51f2f185e8d2700e1573d8a633)

:rocket:

### Step 2: Goals for Publicity

How about we add some goals we need to hit before we can go fully public?

- [ ] Email confirmation
- [ ] URL commonizer to avoid messy URL savings
  > (i.e. www.google.com vs google.com, these should be the same regardless of what the user typed in)
- [ ] Profile Pictures?
- [ ] Hosting the website somewhere
- [ ] Websockets for UTub chatting
- [ ] [Finish this Readme!](https://hackmd.io/2uvlNeFrT-qBu3qiXTcC6w?both)

### Step 3: Reach Goals

> Let's get some reach goals, shall we?

- [ ] RestAPI developed for the backend
- [ ] iOS app developed from the RestAPI
