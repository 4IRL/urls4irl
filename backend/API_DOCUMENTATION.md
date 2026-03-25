## URLS4IRL Backend API Documentation

- Adopted from: https://stubby4j.com/docs/admin_portal.html
- Inspired by Swagger API docs style & structure: https://petstore.swagger.io/#/pet

------------------------------------------------------------------------------------------

### Authentication

All HTTP requests to the API must include a `session` cookie under the header `Cookie`. Containing a cookie that is expired or invalid
will redirect the user to the splash page. AJAX endpoints that accept JSON (`application/json`) require a CSRF token via the `X-Csrftoken` request header.
HTML form endpoints (splash/auth and contact) use `application/x-www-form-urlencoded` and include the CSRF token as a `csrf_token` form field.

------------------------------------------------------------------------------------------

### ID Values

Values that must include an ID cannot contain decimal or negative values.

They must contain a positive, non-zero integer value associated with the given entity.

------------------------------------------------------------------------------------------

### Endpoints

#### Splash Page

<details>
 <summary><code>GET</code> <code><b>/</b></code> <code>(brings users to the splash page to login/register/validate email)</code></summary>

##### Responses

> | http code     | content-type | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `text/html;charset=utf−8` | `Renders the splash page to the user.` | Splash page shown to user. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects user to the /home page.` | User already logged in and email validated. Redirects user to /home page and renders it. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

##### Example cURL

> ```bash
> curl -X GET \
>  https://urls.4irl.app/
> ```

</details>

------------------------------------------------------------------------------------------

#### User Login / Logout

<details>
 <summary><code>GET</code> <code><b>/login</b></code> <code>(renders login modal on splash page)</code></summary>

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `text/html;charset=utf−8`         | `Register form HTML passed as response.` | Frontend takes HTML and renders in register modal. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects user and renders the email confirmation modal to the user.` | If user logged in but not email validated. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects user to the /home page.` | User already logged in and email validated. Redirects user to /home page and renders it. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

##### Example cURL

> ```bash
> curl -X GET \
>  https://urls.4irl.app/login
> ```

</details>

<details>
 <summary><code>POST</code> <code><b>/login</b></code> <code>(logs user in, generates session cookie)</code></summary>

##### Request Payload

Payload content-type should be `application/json`.

CSRF token must be sent in the `X-CSRFToken` request header.

Required JSON body:
> ```json
> {
>     "username": "%username%",
>     "password": "%password%"
> }
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `text/html;charset=utf−8`         | `Provides URL to user home page.` | On successful login, sends user to their home page, and generates a session cookie for them. |
> | `400`         | `application/json`                | `See below.` | Form errors within login form. |
> | `401`         | `application/json`                | `See below.` | User has not email validated. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

###### 400 HTTP Code Response Body - Example

Invalid form data sent with the request.

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to login user.",
>     "errorCode": 2,
>     "errors": [ 
>       "username": ["This field is required."],
>       "password": ["This field is required."]
>     ]
> }
> ```

###### 401 HTTP Code Response Body - Example

> ```json
> {
>     "status": "Failure",
>     "message": "An account already exists with that information but the email has not been validated.",
>     "errorCode": 1,
> }
> ```

##### Example cURL

> ```bash
> curl -X POST \
>  https://urls.4irl.app/login \
>  -H 'Content-Type: application/json' \
>  -H 'X-CSRFToken: CSRF_TOKEN' \
>  -H 'Cookie: YOUR_COOKIE' \
>  -d '{"username": "USERNAME", "password": "PASSWORD"}'
> ```

</details>

<details>
 <summary><code>GET</code> <code><b>/logout</b></code> <code>(logs out the user from their session)</code></summary>

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `302`         | `text/html;charset=utf−8`         | `Redirects user to splash page.` | Redirects user to the splash page and removes their session. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

##### Example cURL

> ```bash
> curl -X GET \
>  https://urls.4irl.app/logout
> ```

</details>

------------------------------------------------------------------------------------------

#### User Registration

<details>
 <summary><code>GET</code> <code><b>/register</b></code> <code>(renders register modal on splash page)</code></summary>

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `text/html;charset=utf−8`         | `Register form HTML passed as response.` | Frontend takes HTML and renders in register modal. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects user and renders the email confirmation modal to the user.` | If user logged in but not email validated. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects user to the /home page.` | User already logged in and email validated. Redirects user to /home page and renders it. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

##### Example cURL

> ```bash
> curl -X GET \
>  https://urls.4irl.app/register
> ```

</details>

<details>
 <summary><code>POST</code> <code><b>/register</b></code> <code>(register user)</code></summary>

##### Request Payload

Payload content-type should be `application/json`.

CSRF token must be sent in the `X-CSRFToken` request header.

Required JSON body:
> ```json
> {
>     "username": "%username%",
>     "email": "%email%",
>     "confirmEmail": "%confirm email%",
>     "password": "%password%",
>     "confirmPassword": "%confirm password%"
> }
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `201`         | `text/html;charset=utf−8`         | `Renders HTML for email validation modal.` | Once a user is registered, they must be email validated. |
> | `400`         | `application/json`                | `See below.` | Form errors within registration form. |
> | `401`         | `application/json`                | `See below.` | User has already created this account but not email validated. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

###### 400 HTTP Code Response Body - Example

Invalid form data sent with the request.

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to register user.",
>     "errorCode": 2,
>     "errors": [ 
>       "username": ["That username is already taken. Please choose another."],
>       "email": ["This field is required."]
>     ]
> }
> ```

###### 401 HTTP Code Response Body - Example

> ```json
> {
>     "status": "Failure",
>     "message": "An account already exists with that information but the email has not been validated.",
>     "errorCode": 1,
> }
> ```

##### Example cURL

> ```bash
> curl -X POST \
>  https://urls.4irl.app/register \
>  -H 'Content-Type: application/json' \
>  -H 'X-CSRFToken: CSRF_TOKEN' \
>  -H 'Cookie: YOUR_COOKIE' \
>  -d '{"username": "USERNAME", "email": "EMAIL", "confirmEmail": "EMAIL", "password": "PASSWORD", "confirmPassword": "PASSWORD"}'
> ```

</details>

<details>
 <summary><code>GET</code> <code><b>/confirm-email</b></code> <code>(renders email confirmation modal)</code></summary>

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `text/html;charset=utf−8`         | `Renders HTML for email validation modal.` | Renders the modal to email validate, if user is logged in but not email validated. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User has not made an account to confirm an email for. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects user to the /home page.` | User already logged in and email validated. Redirects user to /home page and renders it. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

##### Example cURL

> ```bash
> curl -X GET \
>  https://urls.4irl.app/confirm-email \
>  -H 'Cookie: YOUR_COOKIE'
> ```

</details>

<details>
 <summary><code>POST</code> <code><b>/send-validation-email</b></code> <code>(sends validation email to user)</code></summary>

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Email sent to user for validation. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects user to the /home page.` | User already logged in and email validated. Redirects user to /home page and renders it. |
> | `400`         | `application/json`                | `See below.` | Error sending email to given address. |
> | `400`         | `application/json`                | `See below.` | Error with Mailjet service. |
> | `404`         | `text/html;charset=utf−8`         | None | User to send email to does not exist. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |
> | `429`         | `application/json`                | `See below.` | Too many attempts in an hour, or request done in the past minute. |

###### 200 HTTP Code Response Body - Example

> ```json
> {
>     "status": "Success",
>     "message": "Email sent!",
> }
> ```

###### 400 HTTP Code Response Body - Example

> ```json
> {
>     "status": "Failure",
>     "message": "Email could not be sent.",
>     "errorCode": 3
> }
> ```

###### 400 HTTP Code Response Body - Example

> ```json
> {
>     "status": "Failure",
>     "message": "Error with Mailjet service.",
>     "errorCode": 4
> }
> ```

###### 429 HTTP Code Response Body - Example

> ```json
> {
>     "status": "Failure",
>     "message": "Too many attempts, please wait 1 hour",
>     "errorCode": 1,
> }
> ```

###### 429 HTTP Code Response Body - Example

> ```json
> {
>     "status": "Failure",
>     "message": "4 attempts left, please wait 1 minute before sending another email.",
>     "errorCode": 2,
> }
> ```


##### Example cURL

> ```bash
> curl -X POST \
>  https://urls.4irl.app/send-validation-email \
>  -H 'Content-Type: application/x-www-form-urlencoded' \
>  -H 'Cookie: YOUR_COOKIE' \
>  --data-urlencode 'csrf_token=CSRF_TOKEN'
> ```

</details>

<details>
 <summary><code>GET</code> <code><b>/validate/{token}</b></code> <code>(validates user email)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `token` |  required  | string | The JWT that is unique to the user validating their email |

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `302`         | `text/html;charset=utf−8`         | `Redirects user to the /home page.` | User has been email validated. Redirects user to /home page and renders it. |
> | `400`         | `text/html;charset=utf−8`         | `Renders splash page and email validation modal.` | Token expired. Token has been reset. |
> | `404`         | `text/html;charset=utf−8`         | None | Email validation or user for this token does not exist. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

##### Example cURL

> ```bash
> curl -X GET \
>  https://urls.4irl.app/validate/123456789ABCDEFGH
> ```

</details>

<details>
 <summary><code>GET</code> <code><b>/validate/expired</b></code> <code>(resets an expired email validation token and logs the user in)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `token` |  required  | string (query param) | The expired JWT from the email validation link |

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `text/html;charset=utf−8`         | `Renders splash page with expired-token modal.` | Token found, reset, and user logged in. Splash page is rendered with a modal notifying the user that a new validation email has been sent. |
> | `404`         | `text/html;charset=utf−8`         | None | `token` query parameter is absent, or no email validation record exists for the given token. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

##### Example cURL

> ```bash
> curl -X GET \
>  'https://urls.4irl.app/validate/expired?token=123456789ABCDEFGH'
> ```

</details>

------------------------------------------------------------------------------------------

#### Forgot Password

<details>
 <summary><code>GET</code> <code><b>/forgot-password</b></code> <code>(renders forgot password modal)</code></summary>

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `text/html;charset=utf−8`         | `Renders forgot-password modal.` | Displays the forgot password modal to the user. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User has not validated their email. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects user to the /home page.` | User already logged in and email validated. Redirects user to /home page and renders it. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

##### Example cURL

> ```bash
> curl -X GET \
>  https://urls.4irl.app/forgot-password \
>  -H 'Cookie: YOUR_COOKIE'
> ```

</details>

<details>
 <summary><code>POST</code> <code><b>/forgot-password</b></code> <code>(sends password reset email to user)</code></summary>

##### Request Payload

Payload content-type should be `application/json`.

CSRF token must be sent in the `X-CSRFToken` request header.

Required JSON body:
> ```json
> {
>     "email": "%email%"
> }
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below` | Assuming the email was found in the database and was already validated, a reset-password email is sent. |
> | `400`         | `application/json`                | `See below` | Error with Mailjet service. |
> | `401`         | `application/json`                | `See below` | Error in the form data user sent. |
> | `404`         | `application/json`                | `See below` | Unexpected error occurred processing forgot password. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

To not indicate to the user whether a given email or account already exists, the 200 HTTP response is sent even if an invalid 
or missing email is provided. However, the reset-password email is only sent if the email is validated and exists within the database.

> ```json
> {
>     "status": "Success",
>     "message": "If you entered a valid email, you should receive a reset password link soon."
> }
> ```

###### 400 HTTP Code Response Body - Example

> ```json
> {
>     "status": "Failure",
>     "message": "Error with Mailjet service.",
>     "errorCode": 3
> }
> ```

###### 401 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Email is not valid.",
>     "errors": [
>         "email": ["Invalid email address".],
>     ],
>     "errorCode": 1
> }
> ```

###### 404 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Something went wrong.",
>     "errorCode": 2
> }
> ```

##### Example cURL

> ```bash
> curl -X POST \
>  https://urls.4irl.app/forgot-password \
>  -H 'Content-Type: application/json' \
>  -H 'X-CSRFToken: CSRF_TOKEN' \
>  -H 'Cookie: YOUR_COOKIE' \
>  -d '{"email": "EMAIL"}'
> ```

</details>

------------------------------------------------------------------------------------------

#### Reset Password

<details>
 <summary><code>GET</code> <code><b>/reset-password/{token}</b></code> <code>(renders reset password modal)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `token` |  required  | string | The JWT that is unique to the user resetting their password |

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `text/html;charset=utf−8`         | `Renders reset-password modal.` | Displays the reset password modal to the user. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | Token expired. |
> | `404`         | `text/html;charset=utf−8`         | None | Invalid token, invalid user, user not email authenticated. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

##### Example cURL

> ```bash
> curl -X GET \
>  https://urls.4irl.app/reset-password/123456789ABCDEFGH
> ```

</details>

<details>
 <summary><code>POST</code> <code><b>/reset-password/{token}</b></code> <code>(resets user password)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `token` |  required  | string | The JWT that is unique to the user resetting their password |

##### Request Payload

Payload content-type should be `application/json`.

CSRF token must be sent in the `X-CSRFToken` request header.

Required JSON body:
> ```json
> {
>     "newPassword": "%new_password%",
>     "confirmNewPassword": "%confirm_new_password%"
> }
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below` | Password successfully reset. |
> | `400`         | `application/json`                | `See below` | Password and confirm password must be identical . |
> | `404`         | `application/json`                | `See below` | Unexpected error occurred processing reset password. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "status": "Success",
>     "message": "Password reset."
> }
> ```

###### 400 HTTP Code Response Body - Example

> ```json
> {
>     "status": "Failure",
>     "message": "Could not reset the password.",
>     "errors": [
>         "confirmNewPassword": ["Passwords are not identical."],
>     ],
>     "errorCode": 1
> }
> ```

###### 404 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Something went wrong.",
>     "errorCode": 2
> }
> ```

##### Example cURL

> ```bash
> curl -X POST \
>  https://urls.4irl.app/reset-password/ABCDEFGH123456789 \
>  -H 'Content-Type: application/json' \
>  -H 'X-CSRFToken: CSRF_TOKEN' \
>  -H 'Cookie: YOUR_COOKIE' \
>  -d '{"newPassword": "PASSWORD", "confirmNewPassword": "PASSWORD"}'
> ```

</details>

------------------------------------------------------------------------------------------

#### Home Page

<details>
 <summary><code>GET</code> <code><b>/home</b></code> <code>(renders user's home page)</code></summary>

An optional query parameter "UTubID" may be included, indicating the ID of the UTub they are wishing to load.
This query parameter being included does not change the response of this endpoint.
UTub selection via the query parameter is handled on the client side.

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `text/html;charset=utf−8`         | `Renders user's home page.` | Displays the user's home page, with selectable UTubs. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `404`         | `text/html;charset=utf−8`         | None | Unknown error occurred. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |


##### Example cURL

> ```bash
> curl -X GET \
>  https://urls.4irl.app/home \
>  -H 'Cookie: YOUR_COOKIE'
> ```

</details>

------------------------------------------------------------------------------------------

#### UTubs

<details>
 <summary><code>GET</code> <code><b>/utubs</b></code> <code>(gets summary of user's UTubs)</code></summary>

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Returns summary of user's UTubs in JSON format. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `404`         | `text/html;charset=utf−8`         | None | Unknown error occurred. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> { "utubs": [
>       {
>           "id": 1,
>           "name": "utub2",
>           "memberRole": "creator",
>       },
>       {
>           "id": 2,
>           "name": "utub1",
>           "memberRole": "member",
>       }
>   ]
> }
> ```

##### Example cURL

> ```bash
> curl -X GET \
>  https://urls.4irl.app/utubs \
>  -H 'Cookie: YOUR_COOKIE' \
>  -H 'X-Requested-With: XMLHTTPRequest'
> ```

</details>

<details>
 <summary><code>GET</code> <code><b>/utubs/[int:UTubID]</b></code> <code>(get specific UTub information)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `UTubID` |  required  | int ($int64) | The unique ID of the requested UTub |

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successful retrieval of individual UTub data. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `404`         | `text/html;charset=utf−8`         | None | Could not find associated UTub, or user not in requested UTub. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "id": 1,
>     "name": "My UTub",
>     "createdByUserID": 1,
>     "currentUser": 2,
>     "isCreator": false,
>     "createdAt": "04/04/2024 04:04:04",
>     "description": "Here lies the description",
>     "members": [
>         {
>             "id": 1,
>             "username": "member1"
>         },
>         {
>             "id": 2,
>             "username": "member2"
>         }
>     ],
>     "urls": [
>         {
>             "utubUrlID": 1,
>             "urlString": "https://urls.4irl.app",
>             "urlTagIDs": [1, 2, 3],
>             "canDelete": true,           // Can only delete if UTub creator, or adder of URL  
>             "urlTitle": "Title for URL",
>         },
>         {
>             "utubUrlID": 2,
>             "urlString": "https://www.github.com",
>             "urlTagIDs": [2, 3],
>             "canDelete": false,             
>             "urlTitle": "Title for URL",
>         }
>     ],
>     "tags": [
>         {
>             "id": 1,
>             "tagString": "funny",
>         },
>         {
>             "id": 2,
>             "tagString": "nice",
>         },
>         {
>             "id": 3,
>             "tagString": "helpful",
>         }
>     ]
> }
> ```

##### Example cURL

> ```bash
> curl -X GET \
>  https://urls.4irl.app/utubs/1 \
>  -H 'Cookie: YOUR_COOKIE' \
>  -H 'X-Requested-With: XMLHTTPRequest'
> ```

</details>

<details>
 <summary><code>POST</code> <code><b>/utubs</b></code> <code>(create a new UTub)</code></summary>

##### Request Payload

Payload content-type should be `application/json`.

Required JSON body:
> ```json
> {
>     "utubName": "NewUTubName",
>     "utubDescription": "UTubDescription"
> }
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully added a new UTub. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `400`         | `application/json`                | `See below.` | Validation errors in making the new UTub. |
> | `404`         | `application/json`                | `See below.` | Unable to process the form. |
> | `404`         | `text/html;charset=utf−8`         | None | Unknown error occurred. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "status": "Success",
>     "utubID": 1,
>     "utubName": "UTub 1",
>     "utubDescription": "My first UTub",
>     "utubCreatorID": 1,
> }
> ```

###### 400 HTTP Code Response Body - Example

Invalid JSON body sent with the request.

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to make a UTub with that information.",
>     "errorCode": 1,
>     "errors": {
>         "utubName": ["This field is required."],
>     },
> }
> ```

###### 404 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to make a UTub with that information.",
>     "errorCode": 2,
> }
> ```

##### Example cURL

> ```bash
> curl -X POST \
>  https://urls.4irl.app/utubs \
>  -H 'Content-Type: application/json' \
>  -H 'X-Csrftoken: CSRF_TOKEN' \
>  -H 'Cookie: YOUR_COOKIE' \
>  --data-raw '{"utubName": "UTub Name", "utubDescription": "UTub Description"}'
> ```

</details>
<details>
 <summary><code>DELETE</code> <code><b>/utubs/{UTubID}</b></code> <code>(delete a UTub)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `UTubID` |  required  | int ($int64) | The unique ID of the UTub to delete |

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully deleted a UTub. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `403`         | `application/json`                | `See below.` | User must be creator of UTub to delete UTub. |
> | `404`         | `text/html;charset=utf−8`         | None | Unable to find UTub. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "status": "Success",
>     "message": "UTub deleted.",
>     "utubID": 1,
>     "utubName": "UTub 1",
>     "utubDescription": "My first UTub"
> }
> ```

###### 403 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Not authorized.",
> }
> ```

##### Example cURL

> ```bash
> curl -X DELETE \
>  https://urls.4irl.app/utubs/1 \
>  -H 'Cookie: YOUR_COOKIE'
> ```

</details>
<details>
 <summary><code>PATCH</code> <code><b>/utubs/{UTubID}/name</b></code> <code>(update a UTub name)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `UTubID` |  required  | int ($int64) | The unique ID of the UTub to update |

##### Request Payload

Payload content-type should be `application/json`.

Required JSON body:
> ```json
> {
>     "utubName": "NewUTubName"
> }
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully modified a UTub name. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `400`         | `application/json`                | `See below.` | Validation errors when processing new UTub name. |
> | `403`         | `application/json`                | `See below.` | User must be creator of UTub to modify UTub. |
> | `404`         | `application/json`                | `See below.` | Unable to process the form. |
> | `404`         | `text/html;charset=utf−8`         | None | Unable to find UTub. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "status": "Success",
>     "utubID": 1,
>     "utubName": "New UTub Name",
> }
> ```

###### 400 HTTP Code Response Body - Example

Invalid JSON body sent with the request.

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to modify UTub name.",
>     "errorCode": 2,
>     "errors": {
>         "name": ["This field is required."],
>     },
> }
> ```

###### 403 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Not authorized.",
>     "errorCode": 1
> }
> ```

###### 404 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to modify UTub name.",
>     "errorCode": 1,
> }
> ```

##### Example cURL

> ```bash
> curl -X PATCH \
>  https://urls.4irl.app/utubs/1/name \
>  -H 'Content-Type: application/json' \
>  -H 'X-Csrftoken: CSRF_TOKEN' \
>  -H 'Cookie: YOUR_COOKIE' \
>  --data-raw '{"utubName": "UTub Name"}'
> ```

</details>
<details>
 <summary><code>PATCH</code> <code><b>/utubs/{UTubID}/description</b></code> <code>(update a UTub description)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `UTubID` |  required  | int ($int64) | The unique ID of the UTub to update |

##### Request Payload

Payload content-type should be `application/json`.

Required JSON body:
> ```json
> {
>     "utubDescription": "NewUTubDescription"
> }
> ```

The `utubDescription` field is optional and may be `null` or omitted to clear the description.

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully modified the UTub description. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `400`         | `application/json`                | `See below.` | Validation errors when processing new UTub description. |
> | `403`         | `application/json`                | `See below.` | User must be creator of UTub to modify UTub. |
> | `404`         | `application/json`                | `See below.` | Unable to process the form. |
> | `404`         | `text/html;charset=utf−8`         | None | Unable to find UTub. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "status": "Success",
>     "utubID": 1,
>     "utubDescription": "My first UTub"
> }
> ```

###### 400 HTTP Code Response Body

Invalid JSON body sent with the request. The `errors` field is present when Pydantic validation fails (e.g. field too long), and absent when the description field value is `null`.

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to modify UTub description.",
>     "errorCode": 2,
>     "errors": {
>         "description": ["Field cannot be longer than 500 characters."],
>     },
> }
> ```

###### 403 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Not authorized.",
>     "errorCode": 1
> }
> ```

###### 404 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to modify UTub description.",
>     "errorCode": 1,
> }
> ```

##### Example cURL

> ```bash
> curl -X PATCH \
>  https://urls.4irl.app/utubs/1/description \
>  -H 'Content-Type: application/json' \
>  -H 'X-Csrftoken: CSRF_TOKEN' \
>  -H 'Cookie: YOUR_COOKIE' \
>  --data-raw '{"utubDescription": "UTub Description"}'
> ```

</details>

------------------------------------------------------------------------------------------

#### UTub Members

<details>
 <summary><code>POST</code> <code><b>/utubs/{UTubID}/members</b></code> <code>(add a member to a UTub)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `UTubID` |  required  | int ($int64) | The unique ID of the UTub to add a member to |

##### Request Payload

Payload content-type should be `application/json`.

Required JSON body:
> ```json
> {
>     "username": "newMemberName"
> }
> ```


##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully added a member to the UTub. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `400`         | `application/json`                | `See below.` | Validation errors in adding member, or member already in UTub. |
> | `403`         | `application/json`                | `See below.` | Only UTub creators can add members to UTub. |
> | `404`         | `application/json`                | `See below.` | Unable to process the form. |
> | `404`         | `text/html;charset=utf−8`         | None | Unable to find UTub or member. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "status": "Success",
>     "message": "Member added.",
>     "utubID": 1,
>     "member": {
>         "id": 1,
>         "username": "BobJoe"
>     },
> }
> ```

###### 400 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Member already in UTub.",
>     "errorCode": 2,
> }
> ```

###### 400 HTTP Code Response Body

Indicates missing or invalid JSON body sent with the request.

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to add that member to this UTub.",
>     "errorCode": 3,
>     "errors": {
>         "username": ["This field is required."],
>     },
> }
> ```

###### 403 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Not authorized.",
>     "errorCode": 1,
> }
> ```

###### 404 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to add that member to this UTub.",
>     "errorCode": 4,
> }
> ```

##### Example cURL

> ```bash
> curl -X POST \
>  https://urls.4irl.app/utubs/1/members \
>  -H 'Content-Type: application/json' \
>  -H 'X-Csrftoken: CSRF_TOKEN' \
>  -H 'Cookie: YOUR_COOKIE' \
>  --data-raw '{"username": "newMemberName"}'
> ```

</details>

<details>
 <summary><code>DELETE</code> <code><b>/utubs/{UTubID}/members/{userID}</b></code> <code>(remove a member from a UTub)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `UTubID` |  required  | int ($int64) | The unique ID of the UTub to add a member to |
> | `userID` |  required  | int ($int64) | The unique ID of the User being removed |

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully removed a member from the UTub. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `400`         | `application/json`                | `See below.` | UTub creator cannot remove themselves. |
> | `403`         | `application/json`                | `See below.` | Only UTub creators can remove other members. Members can remove themselves. |
> | `404`         | `application/json`                | `See below.` | Requested member to remove not in requested UTub. |
> | `404`         | `text/html;charset=utf−8`         | None | Unable to find UTub or member. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "status": "Success",
>     "message": "Member removed.",
>     "utubID": 1,
>     "member": {
>         "id": 1,
>         "username": "BobJoe"
>     },
> }
> ```

###### 400 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "UTub creator cannot remove themselves.",
>     "errorCode": 1,
> }
> ```

###### 403 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Not allowed to remove a member from this UTub.",
>     "errorCode": 2,
> }
> ```

###### 404 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Member does not exist or not found in this UTub.",
>     "errorCode": 3,
> }
> ```

##### Example cURL

> ```bash
> curl -X DELETE \
>  https://urls.4irl.app/utubs/1/members/2 \
>  -H 'Cookie: YOUR_COOKIE'
> ```

</details>

------------------------------------------------------------------------------------------

#### UTub URLs

<details>
 <summary><code>GET</code> <code><b>/utubs/{UTubID}/urls/{utubUrlID}</b></code> <code>(get details of the UTub URL)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `UTubID` |  required  | int ($int64) | The unique ID of the UTub containing the URL |
> | `utubUrlID` |  required  | int ($int64) | The unique ID of the UTub-URL to get |

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully retrieved the URL. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `403`         | `application/json`                | `See below.` | User not authorized to view this URL in this UTub. |
> | `404`         | `text/html;charset=utf−8`         | None | Unable to find UTub, or URL in UTub. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "status": "Success",
>     "message": "URL found in UTub.",
>     "URL": {
>         "utubUrlID": 1,
>         "urlString": "https://www.google.com",
>         "urlTitle": "This is google.com",
>         "urlTags": [
>           {
>               "tagID": 1,
>               "tagString": "Goodbye"
>           },
>           {
>               "tagID": 2,
>               "tagString": "Hello"
>           },
>         ]
>     }
> }
> ```

###### 403 HTTP Code Response Body

User not member of this UTub.

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to retrieve this URL.",
> }
> ```

###### 404 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to retrieve this URL.",
> }
> ```

##### Example cURL

> ```bash
> curl -X GET \
>  https://urls.4irl.app/utubs/1/urls/2 \
>  -H 'Cookie: YOUR_COOKIE' \
>  -H 'X-Requested-With: XMLHTTPRequest'
> ```

</details>
<details>
 <summary><code>POST</code> <code><b>/utubs/{UTubID}/urls</b></code> <code>(add a URL to a UTub)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `UTubID` |  required  | int ($int64) | The unique ID of the UTub containing the URL |

##### Request Payload

Payload content-type should be `application/json`.

Required JSON body:
> ```json
> {
>     "urlString": "www.google.com",
>     "urlTitle": "This is google"
> }
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully added a URL to a UTub. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `400`         | `application/json`                | `See below.` | URL unable to be validated, or validation errors. |
> | `403`         | `application/json`                | `See below.` | Requesting user not in the requested UTub. |
> | `404`         | `application/json`                | `See below.` | Unable to process the form. |
> | `404`         | `text/html;charset=utf−8`         | None | Unable to find requested UTub. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |
> | `409`         | `application/json`                | `See below.` | URL already in UTub. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "status": "Success",
>     "message": "New URL created and added to UTub." or "URL added to UTub.",
>     "utubID": 1,
>     "addedByUserID": 1, 
>     "URL": {
>         "urlString": "https://urls.4irl.app/",
>         "utubUrlID": 1,
>         "urlTitle": "This is my home page!",
>     }
> }
> ```

###### 400 HTTP Code Response Body

Indicates the URL could not be validated.

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to validate this URL.",
>     "details": "Message describing the connection error.",
>     "errorCode": 2,
> }
> ```

###### 400 HTTP Code Response Body

Indicates validation errors with adding this URL to this UTub.

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to add this URL, please check inputs.",
>     "errorCode": 4,
>     "errors": {
>         "urlString": ["This field is required."],
>         "urlTitle": ["This field is required."],
>     }
> }
> ```

###### 403 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to add this URL.",
>     "errorCode": 1,
> }
> ```

###### 404 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to add this URL.",
>     "errorCode": 5,
> }
> ```

###### 409 HTTP Code Response Body

URL already in UTub.

> ```json
> {
>     "status": "Failure",
>     "message": "URL already in UTub.",
>     "errorCode": 3,
>     "urlString": "https://www.google.com/"  
> }
> ```

##### Example cURL

> ```bash
> curl -X POST \
>  https://urls.4irl.app/utubs/1/urls \
>  -H 'Content-Type: application/json' \
>  -H 'X-Csrftoken: CSRF_TOKEN' \
>  -H 'Cookie: YOUR_COOKIE' \
>  --data-raw '{"urlString": "urls.4irl.app", "urlTitle": "My home page"}'
> ```

</details>
<details>
 <summary><code>DELETE</code> <code><b>/utubs/{UTubID}/urls/{utubUrlID}</b></code> <code>(remove a URL from a UTub)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `UTubID` |  required  | int ($int64) | The unique ID of the UTub containing the URL |
> | `utubUrlID` |  required  | int ($int64) | The unique ID of the Utub-URL to remove from the UTub |

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully removed URL from UTub. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `403`         | `application/json`                | `See below.` | User must be creator of UTub or adder of URL to remove a given URL. |
> | `404`         | `text/html;charset=utf−8`         | None | Unable to find UTub, or URL in UTub. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "status": "Success",
>     "message": "URL removed from this UTub.",
>     "utubID": 1,
>     "URL": {
>         "urlString": "https://urls.4irl.app/",
>         "utubUrlID": 1,
>         "urlTitle": "This is my home page!",
>     },
> }
> ```

###### 403 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to remove this URL.",
> }
> ```

##### Example cURL

> ```bash
> curl -X DELETE \
>  https://urls.4irl.app/utubs/1/urls/1 \
>  -H 'Cookie: YOUR_COOKIE'
> ```

</details>
<details>
 <summary><code>PATCH</code> <code><b>/utubs/{UTubID}/urls/{utubUrlID}</b></code> <code>(update the URL string in a UTub)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `UTubID` |  required  | int ($int64) | The unique ID of the UTub containing the URL |
> | `utubUrlID` |  required  | int ($int64) | The unique ID of the UTub-URL to modify |

##### Request Payload

Payload content-type should be `application/json`.

Required JSON body:
> ```json
> {
>     "urlString": "New URL String"
> }
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully modified the URL string, or no change. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `400`         | `application/json`                | `See below.` | Validation errors, or unable to validate URL. |
> | `403`         | `application/json`                | `See below.` | User must be creator of UTub or adder of URL to modify URL. |
> | `404`         | `application/json`                | `See below.` | Unable to process the form. |
> | `404`         | `text/html;charset=utf−8`         | None | Unable to find UTub, or URL in UTub. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |
> | `409`         | `application/json`                | `See below.` | URL already in UTub. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "status": "Success" or "No change",
>     "message": "URL modified." or "URL not modified",
>     "URL": {
>         "utubUrlID": 1,
>         "urlString": "https://www.google.com",
>         "urlTitle": "This is google.com",
>         "urlTags": [
>           {
>               "tagID": 1,
>               "tagString": "Goodbye"
>           },
>           {
>               "tagID": 2,
>               "tagString": "Hello"
>           },
>         ]
>     }
> }
> ```

###### 400 HTTP Code Response Body

`urlString` cannot contain only whitespace or an empty field.

> ```json
> {
>     "status": "Failure",
>     "message": "URL cannot be empty.",
>     "errorCode": 2,
> }
> ```

###### 400 HTTP Code Response Body

Unable to validate the given URL.

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to validate this URL.",
>     "details": "Message describing the connection error.",
>     "errorCode": 3,
> }
> ```

###### 400 HTTP Code Response Body

Indicates missing or invalid JSON body sent in the request.

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to update, please check inputs.",
>     "errorCode": 5,
>     "errors": {
>         "urlString": ["This field is required."],
>     }
> }
> ```

###### 403 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to modify this URL.",
>     "errorCode": 1
> }
> ```

###### 404 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to update, please check inputs.",
>     "errorCode": 6,
> }
> ```

###### 409 HTTP Code Response Body

URL already in UTub.

> ```json
> {
>     "status": "Failure",
>     "message": "URL already in UTub.",
>     "errorCode": 4,
>     "urlString": "https://www.google.com/"  
> }
> ```

##### Example cURL

> ```bash
> curl -X PATCH \
>  https://urls.4irl.app/utubs/1/urls/1 \
>  -H 'Content-Type: application/json' \
>  -H 'X-Csrftoken: CSRF_TOKEN' \
>  -H 'Cookie: YOUR_COOKIE' \
>  --data-raw '{"urlString": "www.google.com"}'
> ```

</details>

<details>
 <summary><code>PATCH</code> <code><b>/utubs/{UTubID}/urls/{utubUrlID}/title</b></code> <code>(update the title of a URL in a UTub)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `UTubID` |  required  | int ($int64) | The unique ID of the UTub containing the URL |
> | `utubUrlID` |  required  | int ($int64) | The unique ID of the UTub-URL with the title to modify |

##### Request Payload

Payload content-type should be `application/json`.

Required JSON body:
> ```json
> {
>     "urlTitle": "New URL Title"
> }
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully modified the URL title, or no change. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `400`         | `application/json`                | `See below.` | Validation errors with modifying URL title. |
> | `403`         | `application/json`                | `See below.` | User must be creator of UTub or adder of URL to modify title of URL. |
> | `404`         | `application/json`                | `See below.` | Unable to process the form. |
> | `404`         | `text/html;charset=utf−8`         | None | Unable to find UTub, or URL in UTub. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "status": "Success" or "No change",
>     "message": "URL title was modified." or "URL title not modified",
>     "URL": {
>         "utubUrlID": 1,
>         "urlString": "https://www.google.com",
>         "urlTitle": "This is google.com",
>         "urlTags": [
>           {
>               "tagID": 1,
>               "tagString": "Goodbye"
>           },
>           {
>               "tagID": 2,
>               "tagString": "Hello"
>           },
>         ]
>     }
> }
> ```

###### 400 HTTP Code Response Body

Indicates missing JSON field in the request.

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to update, please check inputs.",
>     "errorCode": 2,
>     "errors": {
>         "urlTitle": ["This field is required."],
>     }
> }
> ```

###### 400 HTTP Code Response Body

Indicates invalid JSON field in the request.

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to update, please check inputs.",
>     "errorCode": 3,
>     "errors": {
>         "urlTitle": ["Field cannot be longer than 140 characters."],
>     }
> }
> ```

###### 403 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to modify this URL.",
>     "errorCode": 1
> }
> ```

###### 404 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to update, please check inputs.",
>     "errorCode": 4,
> }
> ```

##### Example cURL

> ```bash
> curl -X PATCH \
>  https://urls.4irl.app/utubs/1/urls/1/title \
>  -H 'Content-Type: application/json' \
>  -H 'X-Csrftoken: CSRF_TOKEN' \
>  -H 'Cookie: YOUR_COOKIE' \
>  --data-raw '{"urlTitle": "New URL title"}'
> ```

</details>

------------------------------------------------------------------------------------------

#### UTub Tags

<details>
 <summary><code>POST</code> <code><b>/utubs/{UTubID}/tags</b></code> <code>(add a tag to a UTub)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `UTubID` |  required  | int ($int64) | The unique ID of the UTub to add tag to |

##### Request Payload

Payload content-type should be `application/json`.

Required JSON body:
> ```json
> {
>     "tagString": "Tag Here"
> }
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully added a tag to UTub. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `400`         | `application/json`                | `See below.` | Validation errors on creation of new tag. |
> | `404`         | `application/json`                | `See below.` | Unable to process the request. |
> | `404`         | `text/html;charset=utf−8`         | None | Unable to find requested UTub. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "status": "Success",
>     "message": "Tag added to this UTub.",
>     "utubTag": {
>         "utubTagID": 1,
>         "tagString": "Hello",
>     },
>     "tagCountsInUtub": 0
> }
> ```

###### 400 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "UTub already contains this tag.",
> }
> ```

###### 400 HTTP Code Response Body

Indicates validation errors with adding this tag to this UTub.

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to add tag to UTub.",
>     "errorCode": 2,
>     "errors": {
>         "tagString": ["This field is required."],
>     }
> }
> ```

###### 404 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to add tag to UTub.",
>     "errorCode": 1,
> }
> ```

##### Example cURL

> ```bash
> curl -X POST \
>  https://urls.4irl.app/utubs/1/tags \
>  -H 'Content-Type: application/json' \
>  -H 'X-Csrftoken: CSRF_TOKEN' \
>  -H 'Cookie: YOUR_COOKIE' \
>  --data-raw '{"tagString": "Hello"}'
> ```

</details>
<details>
 <summary><code>DELETE</code> <code><b>/utubs/{UTubID}/tags/{utubTagID}</b></code> <code>(delete a tag from a UTub)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `UTubID` |  required  | int ($int64) | The unique ID of the UTub to delete tag from |
> | `utubTagID` |  required  | int ($int64) | The unique ID of the utubTag to delete tag from |

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully deleted a tag from UTub, and removed all URL associations with this tag in this UTub. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `404`         | `application/json`                | `See below.` | Unable to process the request. |
> | `404`         | `text/html;charset=utf−8`         | None | Unable to find requested UTub. |
> | `404`         | `text/html;charset=utf−8`         | None | Unable to find requested utubTag. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "status": "Success",
>     "message": "Tag deleted from this UTub.",
>     "utubTag": {
>         "utubTagID": 1,
>         "tagString": "Hello",
>     }
>     "utubUrlIDs": [1, 2, 3]       // IDs of UTubURLs this tag was removed from, can be empty
> }
> ```

##### Example cURL

> ```bash
> curl -X DELETE \
>  https://urls.4irl.app/utubs/1/tags/1 \
>  -H 'Cookie: YOUR_COOKIE'
> ```

</details>

------------------------------------------------------------------------------------------

#### UTub URL Tags

<details>
 <summary><code>POST</code> <code><b>/utubs/{UTubID}/urls/{utubUrlID}/tags</b></code> <code>(add a tag to a URL in a UTub)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `UTubID` |  required  | int ($int64) | The unique ID of the UTub containing the URL |
> | `utubUrlID` |  required  | int ($int64) | The unique ID of the UTub-URL to add the tag to |

##### Request Payload

Payload content-type should be `application/json`.

Required JSON body:
> ```json
> {
>     "tagString": "Tag Here"
> }
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully added a tag to a URL to a UTub. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `400`         | `application/json`                | `See below.` | URL already contains five tags, or validation errors. |
> | `404`         | `application/json`                | `See below.` | Unable to process the form. |
> | `404`         | `text/html;charset=utf−8`         | None | Unable to find requested UTub or given URL or tag in UTub. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "status": "Success",
>     "message": "Tag added to this URL.",
>     "utubUrlTagIDs": [1, 2, 3, 4],      // Contains newly added tag ID
>     "utubTag": {
>         "utubTagID": 4,
>         "tagString": "Hello",
>     },
>     "tagCountsInUtub": 1                // Assumes no other URLs have utubTagID: 4 applied
> }
> ```

###### 400 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "URLs can only have up to 5 tags.",
>     "errorCode": 2,
> }
> ```

###### 400 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "URL already has this tag.",
>     "errorCode": 3,
> }
> ```

###### 400 HTTP Code Response Body

Indicates validation errors with adding this tag onto this URL in this UTub.

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to add tag to URL.",
>     "errorCode": 2,
>     "errors": {
>         "tagString": ["This field is required."],
>     }
> }
> ```

###### 404 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to add tag to URL.",
>     "errorCode": 1,
> }
> ```

##### Example cURL

> ```bash
> curl -X POST \
>  https://urls.4irl.app/utubs/1/urls/1/tags \
>  -H 'Content-Type: application/json' \
>  -H 'X-Csrftoken: CSRF_TOKEN' \
>  -H 'Cookie: YOUR_COOKIE' \
>  --data-raw '{"tagString": "Hello"}'
> ```

</details>
<details>
 <summary><code>DELETE</code> <code><b>/utubs/{UTubID}/urls/{utubUrlID}/tags/{utubTagID}</b></code> <code>(remove a tag from a URL in a UTub)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `UTubID` |  required  | int ($int64) | The unique ID of the UTub containing the URL |
> | `utubUrlID` |  required  | int ($int64) | The unique ID of the UTub-URL with the tag to remove |
> | `utubTagID` |  required  | int ($int64) | The unique ID of the tag to remove |

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully removed the tag from the URL in the UTub. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `404`         | `text/html;charset=utf−8`         | None | Unable to find UTub, URL in UTub, or tag on URL in UTub. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "status": "Success",
>     "message": "Tag removed from this URL.",
>     "utubUrlTagIDs": [1, 2, 3],         // Contains tag ID array of tags still on URL
>     "utubTag": {
>         "utubTagID": 4,
>         "tagString": "Hello",
>     },
>     "tagCountsInUtub": 0                // Assumes no other URLs have utubTagID: 4 applied
> }
> ```

##### Example cURL

> ```bash
> curl -X DELETE \
>  https://urls.4irl.app/utubs/1/urls/1/tags/4 \
>  -H 'Cookie: YOUR_COOKIE'
> ```

</details>

------------------------------------------------------------------------------------------

#### Contact

<details>
 <summary><code>GET</code> <code><b>/contact</b></code> <code>(renders the contact form page)</code></summary>

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `text/html;charset=utf−8`         | `Renders the contact form page.` | Contact form page shown to the user. No authentication required. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

##### Example cURL

> ```bash
> curl -X GET \
>  https://urls.4irl.app/contact
> ```

</details>

<details>
 <summary><code>POST</code> <code><b>/contact</b></code> <code>(submits the contact form)</code></summary>

Rate limited to 5 requests per hour and 10 requests per day per IP address.

##### Request Payload

Payload content-type should be `application/x-www-form-urlencoded; charset=utf−8`.

Required form data:
> ```
> subject: %Subject%
> content: %Message content%
> csrf_token: %csrf_token%
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `text/html;charset=utf−8`         | `Re-renders the contact page.` | Form valid: contact form entry saved and webhook notification sent. Page re-rendered with a flash message: "Sent! Thanks for reaching out." |
> | `200`         | `text/html;charset=utf−8`         | `Re-renders the contact page with inline errors.` | Form invalid: contact page re-rendered with inline validation errors. No flash message. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |
> | `429`         | `text/html;charset=utf−8`         | None | Rate limit exceeded (5/hour or 10/day per IP). |

##### Example cURL

> ```bash
> curl -X POST \
>  https://urls.4irl.app/contact \
>  -H 'Content-Type: application/x-www-form-urlencoded' \
>  --data-urlencode 'subject=Hello there' \
>  --data-urlencode 'content=I have a question about the app.' \
>  --data-urlencode 'csrf_token=CSRF_TOKEN'
> ```

</details>

------------------------------------------------------------------------------------------

#### Legal / Static Pages

<details>
 <summary><code>GET</code> <code><b>/privacy-policy</b></code> <code>(renders the privacy policy page)</code></summary>

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `text/html;charset=utf−8`         | `Renders the privacy policy page.` | No authentication required. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

##### Example cURL

> ```bash
> curl -X GET \
>  https://urls.4irl.app/privacy-policy
> ```

</details>

<details>
 <summary><code>GET</code> <code><b>/terms</b></code> <code>(renders the terms and conditions page)</code></summary>

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `text/html;charset=utf−8`         | `Renders the terms and conditions page.` | No authentication required. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

##### Example cURL

> ```bash
> curl -X GET \
>  https://urls.4irl.app/terms
> ```

</details>

------------------------------------------------------------------------------------------

#### System

<details>
 <summary><code>GET</code> <code><b>/health</b></code> <code>(health check endpoint)</code></summary>

Rate limiting is exempt on this endpoint. No authentication required.

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Service is healthy. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "status": "Success"
> }
> ```

##### Example cURL

> ```bash
> curl -X GET \
>  https://urls.4irl.app/health
> ```

</details>

------------------------------------------------------------------------------------------
