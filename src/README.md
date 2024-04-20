## URLS4IRL Backend API Documentation

- Adopted from: https://stubby4j.com/docs/admin_portal.html
- Inspired by Swagger API docs style & structure: https://petstore.swagger.io/#/pet

------------------------------------------------------------------------------------------

### Authentication

All HTTP requests to the API must include a session cookie under the header `Cookie`. Containing a cookie that is expired or invalid
will redirect the user to the splash page. HTTP requests that use form data require a CSRF token via the `X-Csrftoken` header.

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

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `text/html;charset=utf-8`         | `Renders the splash page to the user.` | Splash page shown to user. |
> | `302`         | `text/html;charset=utf-8`         | `Redirects user to the /home page.` | User already logged in and email validated. Redirects user to /home page and renders it. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

##### Example cURL

> ```bash
> curl -X GET \
>  https://urls4irl.app/ \
> ```

</details>

------------------------------------------------------------------------------------------

#### User Login

<details>
 <summary><code>GET</code> <code><b>/login</b></code> <code>(renders login modal on splash page)</code></summary>

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `text/html;charset=utf-8`         | `Register form HTML passed as response.` | Frontend takes HTML and renders in register modal. |
> | `302`         | `text/html;charset=utf-8`         | `Redirects user and renders the email confirmation modal to the user.` | If user logged in but not email validated. |
> | `302`         | `text/html;charset=utf-8`         | `Redirects user to the /home page.` | User already logged in and email validated. Redirects user to /home page and renders it. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

##### Example cURL

> ```bash
> curl -X GET \
>  https://urls4irl.app/login \
> ```

</details>

<details>
 <summary><code>POST</code> <code><b>/login</b></code> <code>(logs user in, generates session cookie)</code></summary>

##### Request Payload

Payload content-type should be `application/x-www-form-urlencoded; charset=utf-8`.

Required form data:
> ```
> username: %username%
> password: %password%
> csrf_token: %csrf_token%
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `text/html;charset=utf-8`         | `Provides URL to user home page.` | On successful login, sends user to their home page, and generates a session cookie for them. |
> | `400`         | `application/json`                | `See below.` | Form errors within login form. |
> | `401`         | `application/json`                | `See below.` | User has not email validated. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

###### 400 HTTP Code Response Body - Example

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
>  https://urls4irl.app/login \
>  -H 'Content-Type: application/x-www-form-urlencoded' \
>  -H 'Cookie: YOUR_COOKIE' \
>  --data-urlencode 'username=USERNAME' \
>  --data-urlencode 'password=PASSWORD' \
>  --data-urlencode 'csrf_token=CSRF_TOKEN'
> ```

</details>

------------------------------------------------------------------------------------------

#### User Registration

<details>
 <summary><code>GET</code> <code><b>/register</b></code> <code>(renders register modal on splash page)</code></summary>

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `text/html;charset=utf-8`         | `Register form HTML passed as response.` | Frontend takes HTML and renders in register modal. |
> | `302`         | `text/html;charset=utf-8`         | `Redirects user and renders the email confirmation modal to the user.` | If user logged in but not email validated. |
> | `302`         | `text/html;charset=utf-8`         | `Redirects user to the /home page.` | User already logged in and email validated. Redirects user to /home page and renders it. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

##### Example cURL

> ```bash
> curl -X GET \
>  https://urls4irl.app/register \
> ```

</details>

<details>
 <summary><code>POST</code> <code><b>/register</b></code> <code>(register user)</code></summary>

##### Request Payload

Payload content-type should be `application/x-www-form-urlencoded; charset=utf-8`.

Required form data:
> ```
> username: %username%
> email: %email%
> confirmEmail: %confirm email%
> password: %password%
> confirmPassword: %confirm password%
> csrf_token: %csrf_token%
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `201`         | `text/html;charset=utf-8`         | `Renders HTML for email validation modal.` | Once a user is registered, they must be email validated. |
> | `400`         | `application/json`                | `See below.` | Form errors within registration form. |
> | `401`         | `application/json`                | `See below.` | User has already created this account but not email validated. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

###### 400 HTTP Code Response Body - Example

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to register user.",
>     "errorCode": 2 or 3,
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
>  https://urls4irl.app/register \
>  -H 'Content-Type: application/x-www-form-urlencoded' \
>  -H 'Cookie: YOUR_COOKIE' \
>  --data-urlencode 'email=EMAIL' \
>  --data-urlencode 'confirmEmail=EMAIL' \
>  --data-urlencode 'username=USERNAME' \
>  --data-urlencode 'password=PASSWORD' \
>  --data-urlencode 'confirmPassword=PASSWORD'
>  --data-urlencode 'csrf_token=CSRF_TOKEN'
> ```

</details>

<details>
 <summary><code>GET</code> <code><b>/confirm-email</b></code> <code>(renders email confirmation modal)</code></summary>

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `text/html;charset=utf-8`         | `Renders HTML for email validation modal.` | Renders the modal to email validate, if user is logged in but not email validated. |
> | `302`         | `text/html;charset=utf-8`         | `Redirects and renders HTML for splash page.` | User has not made an account to confirm an email for. |
> | `302`         | `text/html;charset=utf-8`         | `Redirects user to the /home page.` | User already logged in and email validated. Redirects user to /home page and renders it. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

##### Example cURL

> ```bash
> curl -X GET \
>  https://urls4irl.app/confirm-email \
>  -H 'Cookie: YOUR_COOKIE' \
> ```

</details>

<details>
 <summary><code>POST</code> <code><b>/send-validation-email</b></code> <code>(sends validation email to user)</code></summary>

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Email sent to user for validation. |
> | `302`         | `text/html;charset=utf-8`         | `Redirects user to the /home page.` | User already logged in and email validated. Redirects user to /home page and renders it. |
> | `400`         | `application/json`                | `See below.` | Error sending email to given address. |
> | `400`         | `application/json`                | `See below.` | Error with Mailjet service. |
> | `404`         | `text/html;charset=utf-8`         | None | User to send email to does not exist. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |
> | `429`         | `application/json`                | `See below.` | Too many attempts in an hour. |

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
>     "errorCode": 1 or 2,
> }
> ```


##### Example cURL

> ```bash
> curl -X POST \
>  https://urls4irl.app/send-validation-email \
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
> | `302`         | `text/html;charset=utf-8`         | `Redirects user to the /home page.` | User has been email validated. Redirects user to /home page and renders it. |
> | `400`         | `text/html;charset=utf-8`         | `Renders splash page and email validation modal.` | Token expired. Token has been reset. |
> | `404`         | `text/html;charset=utf-8`         | None | Email validation or user for this token does not exist. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

##### Example cURL

> ```bash
> curl -X GET \
>  https://urls4irl.app/validate/123456789ABCDEFGH 
> ```

</details>

------------------------------------------------------------------------------------------

#### Forgot Password

<details>
 <summary><code>GET</code> <code><b>/forgot-password</b></code> <code>(renders forgot password modal)</code></summary>

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `text/html;charset=utf-8`         | `Renders forgot-password modal.` | Displays the forgot password modal to the user. |
> | `302`         | `text/html;charset=utf-8`         | `Redirects and renders HTML for splash page.` | User has not validated their email. |
> | `302`         | `text/html;charset=utf-8`         | `Redirects user to the /home page.` | User already logged in and email validated. Redirects user to /home page and renders it. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

##### Example cURL

> ```bash
> curl -X GET \
>  https://urls4irl.app/forgot-password \
>  -H 'Cookie: YOUR_COOKIE' \
> ```

</details>

<details>
 <summary><code>POST</code> <code><b>/forgot-password</b></code> <code>(sends password reset email to user)</code></summary>

##### Request Payload

Payload content-type should be `application/x-www-form-urlencoded; charset=utf-8`.

Required form data:
> ```
> email: %email%
> csrf_token: %csrf_token%
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below` | Assuming the email was found in the database and was already validated, a reset-password email is sent. |
> | `400`         | `application/json`                | `See below` | Error with Mailjet service. |
> | `401`         | `application/json`                | `See below` | Error in the form data user sent. |
> | `404`         | `application/json`                | `See below` | Unexpected error occurred processing forgot password. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

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
>  https://urls4irl.app/forgot-password \
>  -H 'Content-Type: application/x-www-form-urlencoded' \
>  -H 'Cookie: YOUR_COOKIE' \
>  --data-urlencode 'email=EMAIL'
>  --data-urlencode 'csrf_token=CSRF_TOKEN'
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
> | `200`         | `text/html;charset=utf-8`         | `Renders reset-password modal.` | Displays the reset password modal to the user. |
> | `302`         | `text/html;charset=utf-8`         | `Redirects and renders HTML for splash page.` | Token expired. |
> | `404`         | `text/html;charset=utf-8`         | None | Invalid token, invalid user, user not email authenticated. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

##### Example cURL

> ```bash
> curl -X GET \
>  https://urls4irl.app/reset-password/123456789ABCDEFGH \
> ```

</details>

<details>
 <summary><code>POST</code> <code><b>/reset-password/{token}</b></code> <code>(resets user password)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `token` |  required  | string | The JWT that is unique to the user resetting their password |

##### Request Payload

Payload content-type should be `application/x-www-form-urlencoded; charset=utf-8`.

Required form data:
> ```
> newPassword: %new_password%
> confirmNewPassword: %confirm_new_password%
> csrf_token: %csrf_token%
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below` | Password successfully reset. |
> | `400`         | `application/json`                | `See below` | Password and confirm password must be identical . |
> | `404`         | `application/json`                | `See below` | Unexpected error occurred processing reset password. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

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
>  https://urls4irl.app/reset-password/ABCDEFGH123456789 \
>  -H 'Content-Type: application/x-www-form-urlencoded' \
>  -H 'Cookie: YOUR_COOKIE' \
>  --data-urlencode 'newPassword=PASSWORD'
>  --data-urlencode 'confirmNewPassword=PASSWORD'
>  --data-urlencode 'csrf_token=CSRF_TOKEN'
> ```

</details>

------------------------------------------------------------------------------------------

#### Home Page

<details>
 <summary><code>GET</code> <code><b>/home</b></code> <code>(renders user's home page)</code></summary>

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `text/html;charset=utf-8`         | `Renders user's home page, with below JSON embedded.` | Displays the user's home page, with selectable UTubs. |
> | `302`         | `text/html;charset=utf-8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `404`         | `text/html;charset=utf-8`         | None | Unknown error occurred. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

###### 200 HTTP Code JSON Included in HTML Body

The HTML body on a 200 response contains the following JSON.

> ```json
> [
>     {
>         "id": 1,
>         "name": "utub2"
>     },
>     {
>         "id": 2,
>         "name": "utub1"
>     }
> ]
> ```

##### Example cURL

> ```bash
> curl -X GET \
>  https://urls4irl.app/home \
>  -H 'Cookie: YOUR_COOKIE' \
> ```

</details>
<details>
 <summary><code>GET</code> <code><b>/home?UTubID=[int:UTubID]</b></code> <code>(get specific UTub information)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `UTubID` |  required  | int ($int64) | The unique ID of the requested UTub |

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successful retrieval of individual UTub data. |
> | `302`         | `text/html;charset=utf-8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `404`         | `text/html;charset=utf-8`         | None | Could not find associated UTub, or user not in requested UTub. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "id": 1,
>     "name": "My UTub"
>     "createdBy": 1, 
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
>             "urlID": 1,
>             "urlString": "https://urls4irl.app",
>             "urlTags": [1, 2, 3],
>             "addedBy": {
>                 "id": 1,
>                 "username": "member1"
>             },
>             "urlTitle": "Title for URL",
>         },
>         {
>             "urlID": 2,
>             "urlString": "https://www.github.com",
>             "urlTags": [2, 3],
>             "addedBy": {
>                 "id": 2,
>                 "username": "member2"
>             },
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
>  https://urls4irl.app/home?UTubID=1 \
>  -H 'Cookie: YOUR_COOKIE' \
> ```

</details>

------------------------------------------------------------------------------------------

#### UTubs

<details>
 <summary><code>POST</code> <code><b>/utubs</b></code> <code>(create a new UTub)</code></summary>

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully added a new UTub. |
> | `302`         | `text/html;charset=utf-8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `400`         | `application/json`                | `See below.` | Form errors in making the new UTub. |
> | `404`         | `application/json`                | `See below.` | Unable to process the form. |
> | `404`         | `text/html;charset=utf-8`         | None | Unknown error occurred. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

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

###### 400/404 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to make a UTub with that information.",
>     "errorCode": 1 or 2,
>     "errors": {
>         "name": ["This field is required."],
>     },
> }
> ```

##### Example cURL

> ```bash
> curl -X POST \
>  https://urls4irl.app/utubs \
>  -H 'Content-Type: application/x-www-form-urlencoded' \
>  -H 'Cookie: YOUR_COOKIE' \
>  --data-urlencode 'name=UTub Name'
>  --data-urlencode 'description=UTub Description'
>  --data-urlencode 'csrf_token=CSRF_TOKEN'
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
> | `302`         | `text/html;charset=utf-8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `403`         | `application/json`                | `See below.` | User must be creator of UTub to delete UTub. |
> | `404`         | `text/html;charset=utf-8`         | None | Unable to find UTub. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

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
>  https://urls4irl.app/utubs/1 \
>  -H 'Cookie: YOUR_COOKIE' \
> ```

</details>
<details>
 <summary><code>PATCH</code> <code><b>/utubs/{UTubID}/name</b></code> <code>(edit a UTub name)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `UTubID` |  required  | int ($int64) | The unique ID of the UTub to edit |

##### Request Payload

Payload content-type should be `application/x-www-form-urlencoded; charset=utf-8`.

Required form data:
> ```
> name: %NewUTubName%
> csrf_token: %csrf_token%
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully modified a UTub name. |
> | `302`         | `text/html;charset=utf-8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `400`         | `application/json`                | `See below.` | Form errors when processing new UTub name. |
> | `403`         | `application/json`                | `See below.` | User must be creator of UTub to modify UTub. |
> | `404`         | `application/json`                | `See below.` | Unable to process the form. |
> | `404`         | `text/html;charset=utf-8`         | None | Unable to find UTub. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "status": "Success",
>     "utubID": 1,
>     "utubName": "New UTub Name",
>     "utubDescription": "My first UTub"
> }
> ```

###### 400 HTTP Code Response Body

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
>     "errorCode": 3,
> }
> ```

##### Example cURL

> ```bash
> curl -X PATCH \
>  https://urls4irl.app/utubs/1/name \
>  -H 'Content-Type: application/x-www-form-urlencoded' \
>  -H 'Cookie: YOUR_COOKIE' \
>  --data-urlencode 'name=UTub Name'
>  --data-urlencode 'csrf_token=CSRF_TOKEN'
> ```

</details>
<details>
 <summary><code>PATCH</code> <code><b>/utubs/{UTubID}/description</b></code> <code>(edit a UTub description)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `UTubID` |  required  | int ($int64) | The unique ID of the UTub to edit |

##### Request Payload

Payload content-type should be `application/x-www-form-urlencoded; charset=utf-8`.

Required form data:
> ```
> name: %NewUTubName%
> csrf_token: %csrf_token%
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully modified the UTub description. |
> | `302`         | `text/html;charset=utf-8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `400`         | `application/json`                | `See below.` | Form errors when processing new UTub description. |
> | `403`         | `application/json`                | `See below.` | User must be creator of UTub to modify UTub. |
> | `404`         | `application/json`                | `See below.` | Unable to process the form. |
> | `404`         | `text/html;charset=utf-8`         | None | Unable to find UTub. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "status": "Success",
>     "utubID": 1,
>     "utubName": "New UTub Name",
>     "utubDescription": "My first UTub"
> }
> ```

###### 400 HTTP Code Response Body

Indicates a missing form field in the payload content.

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to modify UTub description.",
>     "errorCode": 2,
> }
> ```

###### 400 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to modify UTub description.",
>     "errorCode": 3,
>     "errors": {
>         "name": ["Field cannot be longer than 500 characters."],
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
>     "errorCode": 4,
> }
> ```

##### Example cURL

> ```bash
> curl -X PATCH \
>  https://urls4irl.app/utubs/1/description \
>  -H 'Content-Type: application/x-www-form-urlencoded' \
>  -H 'Cookie: YOUR_COOKIE' \
>  --data-urlencode 'description=UTub Description'
>  --data-urlencode 'csrf_token=CSRF_TOKEN'
> ```

</details>
<details>
 <summary><code>GET</code> <code><b>/home?UTubID=[int:UTubID]</b></code> <code>(get specific UTub information)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `UTubID` |  required  | int ($int64) | The unique ID of the requested UTub |

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successful retrieval of individual UTub data. |
> | `302`         | `text/html;charset=utf-8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `400`         | `application/json`                | `See below.` | Form errors in making the new UTub. |
> | `404`         | `text/html;charset=utf-8`         | None | Could not find associated UTub, or user not in requested UTub. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "id": 1,
>     "name": "My UTub"
>     "createdBy": 1, 
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
>             "urlID": 1,
>             "urlString": "https://urls4irl.app",
>             "urlTags": [1, 2, 3],
>             "addedBy": {
>                 "id": 1,
>                 "username": "member1"
>             },
>             "urlTitle": "Title for URL",
>         },
>         {
>             "urlID": 2,
>             "urlString": "https://www.github.com",
>             "urlTags": [2, 3],
>             "addedBy": {
>                 "id": 2,
>                 "username": "member2"
>             },
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
>  https://urls4irl.app/home?UTubID=1 \
>  -H 'Cookie: YOUR_COOKIE' \
> ```

</details>

------------------------------------------------------------------------------------------

#### Users and Project Management

<details>
 <summary><code>GET</code> <code><b>/projects/{projectID}/users</b></code> <code>(gets all users associated with a project)</code>:white_check_mark:</summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `projectID` |  required  | int ($int64) | The unique ID of the project |

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Returns all users associated with a project. |
> | `403`         | `application/json`                | `{"code":"403","message":"User not in this project, or project does not exist"}` | User not in this project, or project does not exist. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "projectName": "project1",
>     "projectID": 1,
>     "lastUpdated": "2023-10-31T15:45:00Z",
>     "projectLocation": "/api/v1/projects/1",
>     "team": {
>         "teamName": "Team1",
>         "teamID": 1,
>         "teamLocation": "/api/v1/teams/1"
>      },
>     "users": [
>       {
>           "username": "username1",
>           "userID": 1
>       },
>       {
>           "username": "username2",
>           "userID": 2
>       },
>     ],
>     "currentUser": {
>         "username": "username1",
>         "userID": 1,
>         "userProjectID": 1
>      },
> }
> ```

##### Example cURL

> ```bash
> curl -X GET \
>  https://opm-api.propersi.me/api/v1/projects/1/users \
>  -H 'Authorization: Bearer YOUR_JWT_TOKEN' \
> ```

</details>

<details>
 <summary><code>POST</code> <code><b>/projects/{projectID}/users</b></code> <code>(add user to project)</code>:white_check_mark:</summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `projectID` |  required  | int ($int64) | The unique ID of the project |

##### Request Payload

> ```json
> {
>   "username": "username-here"
> }
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `{"code":"200","message":"{username} added to the project."}` | Successfully added user to project. |
> | `403`         | `application/json`                | `{"code":"403","message":"User not in this project, or project does not exist"}` | User trying to add other user is not in project, or project does not exist. |
> | `404`         | `application/json`                | `{"code":"404","message":"User does not exist"}` | Username not found. |
> | `409`         | `application/json`                | `{"code":"409","message":"User already in this project"}` | User already in this project. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

##### Example cURL

> ```bash
> curl -X POST \
>  https://opm-api.propersi.me/api/v1/projects/1/user \
>  -H 'Content-Type: application/json' \
>  -H 'Authorization: Bearer YOUR_JWT_TOKEN' \
>  -d '{"username":"another_username"}' 
> ```

</details>

<details>
 <summary><code>DELETE</code> <code><b>/projects/{projectID}/users</b></code> <code>(remove user from project)</code>:white_check_mark:</summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `projectID` |  required  | int ($int64) | The unique ID of the project |

##### Request Payload

> ```json
> {
>   "username": "username-here"
> }
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `{"code":"200","message":"{username} was removed from the project"}` | Successfully removed user from project. |
> | `400`         | `application/json`                | `{"code":"400","message":"The last member of a project cannot remove themselves"}` | The last user of a project cannot remove themselves. |
> | `403`         | `application/json`                | `{"code":"403","message":"User not in project, or project does not exist"}` | Deleting user not in project, or project does not exist. |
> | `404`         | `application/json`                | `{"code":"404","message":"User not in this project"}` | Username not found. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

##### Example cURL

> ```bash
> curl -X DELETE \
>  https://opm-api.propersi.me/api/v1/projects/1/user \
>  -H 'Content-Type: application/json' \
>  -H 'Authorization: Bearer YOUR_JWT_TOKEN' \
>  -d '{"username":"another_username"}' 
> ```

</details>

------------------------------------------------------------------------------------------

#### Columns Management

<details>
 <summary><code>POST</code> <code><b>/projects/{projectID}/columns</b></code> <code>(adds a column to a project)</code>:white_check_mark:</summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `projectID` |  required  | int ($int64) | The unique ID of the project |

##### Request Payload

> ```json
> {
>   "columnTitle": "New Column Here"
> }
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `201`         | `application/json`                | `See below.` | **Includes a URI to the column resource in the Location Header** |
> | `403`         | `application/json`                | `{"code":"403","message":"User not in project, or project does not exist"}` | User not in this project, or project does not exist. |
> | `409`         | `application/json`                | `{"code":"409","message":"Given column title already exists in this project"}` | Column title already exists in project. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

###### 201 HTTP Code Response Body

> ```json
> {
>     "columnTitle": "New Column Here",
>     "columnIndex": 1,         # New column always placed at end
>     "columnID": 1,
>     "columnLocation": "/api/v1/projects/1/columns/1"
> }
> ```

##### Example cURL

> ```bash
> curl -X POST \
>  https://opm-api.propersi.me/api/v1/project/1/columns \
>  -H 'Content-Type: application/json' \
>  -H 'Authorization: Bearer YOUR_JWT_TOKEN' \
>  -d '{"columnTitle":"New Column Here"}' 
> ```

</details>

<details>
 <summary><code>PUT</code> <code><b>/projects/{projectID}/columns/{columnID}/name</b></code> <code>(modifies column name)</code>:white_check_mark:</summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `projectID` |  required  | int ($int64) | The unique ID of the project |
> | `columnID` |  required  | int ($int64) | The unique ID of the column |

##### Request Payload

> ```json
> {
>   "columnTitle": "New Column Name Here"       # Cannot be deleted, only modified
> }
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully modified column name in project. |
> | `400`         | `application/json`                | `{"code":"400","message":"Column title not changed, title identical to previous"}` | Column title to change to, same as previous title. |
> | `403`         | `application/json`                | `{"code":"403","message":"User not in this project, or project does not exist"}` | User not in this project, or project does not exist. |
> | `404`         | `application/json`                | `{"code":"404","message":"Given column does not exist in project"}` | Column not found in project. |
> | `409`         | `application/json`                | `{"code":"409","message":"Given column title already exists in project"}` | Column title already exists in project. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "columnTitle": "New Column Name Here",
>     "columnIndex": 0,      # Keeps previous column index
>     "columnID": 1,
>     "columnLocation": "/api/v1/projects/1/columns/1
> }
> ```

##### Example cURL

> ```bash
> curl -X PUT \
>  https://opm-api.propersi.me/api/v1/projects/1/columns/1/name \
>  -H 'Content-Type: application/json' \
>  -H 'Authorization: Bearer YOUR_JWT_TOKEN' \
>  -d '{"columnTitle":"New Column Name Here"}' 
> ```

</details>

<details>
 <summary><code>PUT</code> <code><b>/projects/{projectID}/columns/{columnID}/order</b></code> <code>(modifies column order)</code>:white_check_mark:</summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `projectID` |  required  | int ($int64) | The unique ID of the project |
> | `columnID` |  required  | int ($int64) | The unique ID of the column |

##### Request Payload

> ```json
> {
>   "columnIndex": 1
> }
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully modified column index in project. |
> | `400`         | `application/json`                | `{"code":"400","message":"New column index given is same as current column index"}` | New column index is same as previous. |
> | `403`         | `application/json`                | `{"code":"403","message":"Not authorized"}` | User not in this project. |
> | `404`         | `application/json`                | `{"code":"404","message":"Project does not exist"}` | Project not found. |
> | `404`         | `application/json`                | `{"code":"404","message":"Column does not exist"}` | Column not found in project. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "columnTitle": "project1",
>     "columnIndex": 0,      # The new index
>     "columnID": 1,
>     "columnLocation": "/api/v1/projects/1/columns/1
> }
> ```

##### Example cURL

> ```bash
> curl -X PUT \
>  https://opm-api.propersi.me/api/v1/projects/1/columns/1/name \
>  -H 'Content-Type: application/json' \
>  -H 'Authorization: Bearer YOUR_JWT_TOKEN' \
>  -d '{"columnTitle":"New Column Name Here"}' 
> ```

</details>

<details>
 <summary><code>DELETE</code> <code><b>/projects/{projectID}/columns/{columnID}</b></code> <code>(deletes a column from a project, decrements column index for columns following this column in-order)</code>:white_check_mark:</summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `projectID` |  required  | int ($int64) | The unique ID of the project |
> | `columnID` |  required  | int ($int64) | The unique ID of the column |

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `{"code":"200","message":"Column removed from project"}` | Successfully deleted column from project. |
> | `403`         | `application/json`                | `{"code":"403","message":"Cannot remove if tasks remain in column"}` | Tasks still in column. |
> | `403`         | `application/json`                | `{"code":"403","message":"User not in project, or project does not exist"}` | User not in this project, or project does not exist. |
> | `404`         | `application/json`                | `{"code":"404","message":"Column does not exist"}` | Column not found in project. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |


##### Example cURL

> ```bash
> curl -X DELETE \
>  https://opm-api.propersi.me/api/v1/projects/1/columns/1 \
>  -H 'Authorization: Bearer YOUR_JWT_TOKEN' \
> ```

</details>

------------------------------------------------------------------------------------------

#### Task Management

<details>
 <summary><code>POST</code> <code><b>/projects/{projectID}/tasks</b></code> <code>(adds task to column in project)</code>:white_check_mark:</summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `projectID` |  required  | int ($int64) | The unique ID of the project |

##### Request Payload

> ```json
> {
>     "title": "Task 1",
>     "description": "This is another task!", # Optional - a description of only spaces is considered null
>     "columnID": 1,                          # Optional, defaults to first in-order column if not included
>     "assignedTo": 1,                        # Optional, userProjectID of the user who it is being assigned to, or null
>     "dueDate": "2024-11-03",                # Optional, in format "yyyy-MM-dd"
>     "priority": "High",                     # Optional, must be one of: 'High', 'Medium', 'Low', 'None', defaults to 'None' 
>     "sprintID": 1,                          # Optional
>     "customFields": [ ... ]                 # Optional
> }
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `201`         | `application/json`                | `See below.` | **Includes a URI to the task resource in the Location Header** |
> | `403`         | `application/json`                | `{"code":"403","message":"User not in this project, or project not found"}` | User not in this project, or project not found. |
> | `404`         | `application/json`                | `{"code":"404","message":"Column does not exist"}` | Column not found in project. Project must have at least one column. |
> | `404`         | `application/json`                | `{"code":"404","message":"Sprint not found"}` | Sprint not found. |
> | `404`         | `application/json`                | `{"code":"404","message":"Assigned-to user not in this project, or user does not exist"}` | Assignee not found. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

###### 201 HTTP Code Response Body

> ```json
> {
>     "title": "Task 1",
>     "taskID": 1,
>     "columnID": 1,                          # ID of column to be placed under
>     "priority": "None",                     # Other possible values: 'High', 'Medium', 'Low'
>     "description": "None",                  # Nullable
>     "dueDate": "None",                      # Nullable
>     "sprintID": "None",                     # Nullable
>     "assignedTo": "None",                   # Nullable
>     "taskLocation": "/api/v1/projects/1/tasks/1",
> }
> ```

##### Example cURL

> ```bash
> curl -X POST \
>  https://opm-api.propersi.me/api/v1/projects/1/tasks \
>  -H 'Content-Type: application/json' \
>  -H 'Authorization: Bearer YOUR_JWT_TOKEN' \
>  -d '{"title":"Task title"}' 
> ```

</details>

<details>
 <summary><code>GET</code> <code><b>/projects/{projectID}/tasks/{taskID}</b></code> <code>(gets specific task details in a project)</code>:white_check_mark:</summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `projectID` |  required  | int ($int64) | The unique ID of the project |
> | `taskID` |  required  | int ($int64) | The unique ID of the task |

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully retrieved the task details. |
> | `403`         | `application/json`                | `{"code":"403","message":"User not in this project, or project does not exist"}` | User not in this project, or project does not exist. |
> | `404`         | `application/json`                | `{"code":"404","message":"Given task does not exist in this project"}` | Task not found. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "title": "Task 1",
>     "taskID": 1,
>     "taskColumnIndex": 0,         # Indicates location on board
>     "column": {
>           "columnTitle": "Column",
>           "columnIndex": 0,
>           "columnID": 1,
>           "columnLocation": "api/v1/projects/1/columns/1"
>      },
>     "description": "This is a task!",
>     "assignedTo": {               # Or null
>           "username": "username-of-assignee",
>           "userID": 1,
>           "userProjectID": 1
>      },       
>     "priority": "High",
>     "dueDate": "2023-10-31"       # Or null,
>     "sprint": {                   # Or null,
>           "startDate": "2023-10-31",
>           "endDate": "2023-11-01",
>           "sprintName": "Sprint Name",
>           "sprintID": 1,
>           "sprintLocation": "api/v1/projects/1/sprints/1"
>      },
>     "comments": [
>      {
>           "commentID": 1,
>           "commentBody": "This is a comment",
>           "commentedAt": "2023-10-31T15:45:00Z",
>           "commenterUsername": "username-here",
>           "commenterID": 1,
>           "commentLocation": "/api/v1/projects/1/tasks/1/comments/1"
>      },
>     ],
>     "customFields": [ ... ],
>     "taskLocation": "/api/v1/projects/1/tasks/1",
> }
> ```

##### Example cURL

> ```bash
> curl -X GET \
>  https://opm-api.propersi.me/api/v1/projects/1/tasks/1 \
>  -H 'Authorization: Bearer YOUR_JWT_TOKEN' \
> ```

</details>

<details>
 <summary><code>PUT</code> <code><b>/projects/{projectID}/tasks/{taskID}</b></code> <code>(modifies task in column in project)</code>:white_check_mark:</summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `projectID` |  required  | int ($int64) | The unique ID of the project |
> | `taskID` |  required  | int ($int64) | The unique ID of the task |

##### Request Payload

To keep the attribute the same, do not include the task attribute in the request payload.
To delete the attribute, set the attribute to null in the request payload.

> ```json
> {
>     "title": "New Title",                     # Optional - note that a title is mandatory for a task, so no possibility of deleting a title
>     "description": "This is another task!",   # Optional
>     "assignedTo": 1,                          # Optional, userProjectID of the user who it is being assigned to
>     "priority": "High",                       # Optional, must be one of 'High', 'Medium', 'Low', 'None'
>     "sprintID": 1,                            # Optional, ID of sprint to change to
>     "dueDate": "2024-08-08",                  # Optional, new due date
>     "customFields": [ ... ],                  # Optional, for future implementation
> }
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `{"code":"200","message":"Task successfully modified"}` | Successfully modified task. |
> | `200`         | `application/json`                | `{"code":"200","message":"Task was not modified"}` | Server processed request but did not find any differences in the task. |
> | `403`         | `application/json`                | `{"code":"403","message":"User not in this project, or project does not exist"}` | User not in this project, or project does not exist. |
> | `404`         | `application/json`                | `{"code":"404","message":"Task does not exist"}` | Task not found. |
> | `404`         | `application/json`                | `{"code":"404","message":"Task field to modify not valid"}` | Task attribute not found. |
> | `404`         | `application/json`                | `{"code":"404","message":"Given sprint does not exist in this project"}` | Sprint not found. |
> | `404`         | `application/json`                | `{"code":"404","message":"Assigned-to user not in project, or user does not exist"}` | Assignee not found, or does not exist. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

##### Example cURL

> ```bash
> curl -X PUT \
>  https://opm-api.propersi.me/api/v1/projects/1/tasks/1 \
>  -H 'Content-Type: application/json' \
>  -H 'Authorization: Bearer YOUR_JWT_TOKEN' \
>  -d '{"title":"New title."}' 
> ```

</details>

<details>
 <summary><code>PUT</code> <code><b>/project/{projectID}/tasks/{taskID}/columns/{columnID}</b></code> <code>(moves task to other column in project)</code>:white_check_mark:</summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `projectID` |  required  | int ($int64) | The unique ID of the project |
> | `taskID` |  required  | int ($int64) | The unique ID of the task |
> | `columnID` |  required  | int ($int64) | The unique ID of the column |

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `{"code":"200","message":"Task moved"}` | Successfully moved task. |
> | `400`         | `application/json`                | `{"code":"400","message":"Task already in given column"}` | Task already in the column indicated. |
> | `403`         | `application/json`                | `{"code":"403","message":"User not in project, or project does not exist"}` | User not in this project, or project does not exist. |
> | `404`         | `application/json`                | `{"code":"404","message":"Task does not exist"}` | Task not found in project. |
> | `404`         | `application/json`                | `{"code":"404","message":"Column does not exist"}` | Column not found in project. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

##### Example cURL

> ```bash
> curl -X PUT \
>  https://opm-api.propersi.me/api/v1/projects/1/tasks/1/columns/1 \
>  -H 'Authorization: Bearer YOUR_JWT_TOKEN' \
> ```

</details>

<details>
 <summary><code>DELETE</code> <code><b>/project/{projectID}/tasks/{taskID}</b></code> <code>(removes task from project)</code>:white_check_mark:</summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `projectID` |  required  | int ($int64) | The unique ID of the project |
> | `taskID` |  required  | int ($int64) | The unique ID of the task |

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `{"code":"200","message":"Task deleted"}` | Successfully deleted task. |
> | `403`         | `application/json`                | `{"code":"403","message":"User not in project, or project does not exist"}` | User not in this project, or project does not exist |
> | `404`         | `application/json`                | `{"code":"404","message":"Task does not exist"}` | Task not found in project. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

##### Example cURL

> ```bash
> curl -X DELETE \
>  https://opm-api.propersi.me/api/v1/projects/1/tasks/1 \
>  -H 'Authorization: Bearer YOUR_JWT_TOKEN' \
> ```

</details>

------------------------------------------------------------------------------------------

#### Comment Management

<details>
 <summary><code>POST</code> <code><b>/projects/{projectID}/tasks/{taskID}/comments</b></code> <code>(add a comment to a task)</code>:white_check_mark:</summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `projectID` |  required  | int ($int64) | The unique ID of the project |
> | `taskID` |  required  | int ($int64) | The unique ID of the task |

##### Request Payload

> ```json
> {
>     "commentBody": "New comment body."    # Cannot be empty or just spaces
> }
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `201`         | `application/json`                | `See below.` | **Includes a URI to the comment resource in the Location Header** |
> | `400`         | `application/json`                | `{"code":"400","message":"Comment cannot be empty"}` | Comment cannot be empty. |
> | `403`         | `application/json`                | `{"code":"403","message":"User not in this project, or project does not exist"}` | User not in this project, or project does not exist. |
> | `404`         | `application/json`                | `{"code":"404","message":"Given task does not exist in this project"}` | Task not found. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

###### 201 HTTP Code Response Body

> ```json
> {
>     "commentID": 1,
>     "commentBody": "This is a comment.",
>     "commentedAt": "This is a comment.",
>     "commenterUsername": "This is a comment.",
>     "commenterID": "This is a comment.",
> }
> ```

##### Example cURL

> ```bash
> curl -X POST \
>  https://opm-api.propersi.me/api/v1/projects/1/tasks/1/comments \
>  -H 'Content-Type: application/json' \
>  -H 'Authorization: Bearer YOUR_JWT_TOKEN' \
>  -d '{"commentBody":"New comment stuff."}' 
> ```

</details>

<details>
 <summary><code>PUT</code> <code><b>/projects/{projectID}/tasks/{taskID}/comments/{commentID}</b></code> <code>(modify a comment on a task)</code>:white_check_mark:</summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `projectID` |  required  | int ($int64) | The unique ID of the project |
> | `taskID` |  required  | int ($int64) | The unique ID of the task |
> | `commentID` |  required  | int ($int64) | The unique ID of the comment |

##### Request Payload

> ```json
> {
>     "commentBody": "New comment body."    # Cannot be empty or just spaces
> }
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `{"code":"200","message":"Comment modified."}` | Successfully edited the comment. |
> | `403`         | `application/json`                | `{"code":"403","message":"User not in project, or project does not exist"}` | User not in this project. |
> | `403`         | `application/json`                | `{"code":"403","message":"User did not leave this comment"}` | User did not leave this comment. |
> | `404`         | `application/json`                | `{"code":"404","message":"Comment not found on task"}` | Comment not found. |
> | `404`         | `application/json`                | `{"code":"404","message":"Given task does not exist in this project"}` | Task not found. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

##### Example cURL

> ```bash
> curl -X PUT \
>  https://opm-api.propersi.me/api/v1/projects/1/tasks/1/comments/1 \
>  -H 'Content-Type: application/json' \
>  -H 'Authorization: Bearer YOUR_JWT_TOKEN' \
>  -d '{"commentBody":"New comment stuff."}' 
> ```

</details>

<details>
 <summary><code>DELETE</code> <code><b>/projects/{projectID}/tasks/{taskID}/comments/{commentID}</b></code> <code>(delete a comment on a task)</code>:white_check_mark:</summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `projectID` |  required  | int ($int64) | The unique ID of the project |
> | `taskID` |  required  | int ($int64) | The unique ID of the task |
> | `commentID` |  required  | int ($int64) | The unique ID of the comment |

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `{"code":"200","message":"Comment deleted."}` | Successfully deleted the comment. |
> | `403`         | `application/json`                | `{"code":"403","message":"Not authorized"}` | User not in this project. |
> | `404`         | `application/json`                | `{"code":"404","message":"Comment does not exist"}` | Comment not found. |
> | `404`         | `application/json`                | `{"code":"404","message":"Task does not exist"}` | Task not found. |
> | `404`         | `application/json`                | `{"code":"404","message":"Project does not exist"}` | Project not found. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

##### Example cURL

> ```bash
> curl -X DELETE \
>  https://opm-api.propersi.me/api/v1/projects/1/tasks/1/comments/1 \
>  -H 'Authorization: Bearer YOUR_JWT_TOKEN' \
> ```

</details>

------------------------------------------------------------------------------------------

#### Sprint Management

<details>
 <summary><code>GET</code> <code><b>/projects/{projectID}/sprints</b></code> <code>(gets all sprints associated with a project)</code>:white_check_mark:</summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `projectID` |  required  | int ($int64) | The unique ID of the project |

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully retrieved all sprints for the task. |
> | `403`         | `application/json`                | `{"code":"403","message":"User not in this project, or project does not exist"}` | User not in this project, or project does not exist. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

Sprints are ordered in ascending order by sprint end date.

> ```json
> {
>     "projectName": "MyProjectName",
>     "projectID": 1,
>     "projectLocation": "/api/v1/projects/1",
>     "sprints": [
>      {
>           "sprintID": 1,
>           "sprintName": "Sprint Name1",
>           "startDate": "2023-10-31",
>           "endDate": "2023-11-15",
>           "sprintLocation": "/api/v1/projects/1/sprints/1"
>      },
>      {
>           "sprintID": 2,
>           "sprintName": "Sprint Name2",
>           "startDate": "2023-10-31",
>           "endDate": "2023-11-16",
>           "sprintLocation": "/api/v1/projects/1/sprints/2"
>      },
>     ]
> }
> ```

##### Example cURL

> ```bash
> curl -X GET \
>  https://opm-api.propersi.me/api/v1/projects/1/sprints \
>  -H 'Authorization: Bearer YOUR_JWT_TOKEN' \
> ```

</details>

<details>
 <summary><code>POST</code> <code><b>/projects/{projectID}/sprints</b></code> <code>(adds a sprint to a project)</code>:white_check_mark:</summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `projectID` |  required  | int ($int64) | The unique ID of the project |

##### Request Payload

> ```json
> {
>     "startDate": "2023-11-15",
>     "endDate": "2023-11-30",
>     "sprintName": "Sprint Name"
> }
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `201`         | `application/json`                | `See below.` | **Includes a URI to the sprint resource in the Location Header** |
> | `400`         | `application/json`                | `{"code":"400","message":"Sprint dates are invalid"}` | Invalid date range for sprint. |
> | `403`         | `application/json`                | `{"code":"403","message":"Not authorized"}` | User not in this project. |
> | `404`         | `application/json`                | `{"code":"404","message":"Project does not exist"}` | Project not found. |
> | `409`         | `application/json`                | `{"code":"409","message":"Project contains sprint with that name already"}` | Sprint name must be unique for this project. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

###### 201 HTTP Code Response Body

> ```json
> {
>     "sprintID": 1,
>     "startDate": "2023-11-15",
>     "endDate": "2023-11-30",
>     "sprintName": "Sprint Name"
> }
> ```

##### Example cURL

> ```bash
> curl -X POST \
>  https://opm-api.propersi.me/api/v1/projects/1/sprints \
>  -H 'Content-Type: application/json' \
>  -H 'Authorization: Bearer YOUR_JWT_TOKEN' \
>  -d '{
>   "sprintName": "Sprint name",
>   "startDate": "2023-11-15",
>   "endDate": "2023-11-30",
>      }' 
> ```

</details>

<details>
 <summary><code>GET</code> <code><b>/projects/{projectID}/sprints/{sprintID}</b></code> <code>(get all tasks associated with a sprint in a project)</code>:white_check_mark:</summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `projectID` |  required  | int ($int64) | The unique ID of the project |
> | `sprintID` |  required  | int ($int64) | The unique ID of the sprint |

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully retrieved all tasks for the sprint. |
> | `403`         | `application/json`                | `{"code":"403","message":"User not in this project, or project does not exist"}` | User not in this project, or project does not exist. |
> | `404`         | `application/json`                | `{"code":"404","message":"Given sprint does not exist in this project"}` | Sprint not found. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "sprintID": 1,
>     "sprintName": "Sprint Name",
>     "startDate": "2023-10-31",
>     "endDate": "2023-11-15",
>     "sprintLocation": "/api/v1/projects/1/sprints/1",
>     "tasks": [
>      {
>           "title": "Task 1",
>           "taskID": 1,
>           "priority": "High",
>           "dueDate": "2024-08-08",
>           "description": "This is a task!",
>           "comments": 1,
>           "column": {
>                 "columnTitle": "Column title",
>                 "columnID": 1,
>                 "columnIndex": 1,
>                 "columnLocation": "/api/v1/projects/1/columns/1"
>            },
>           "assignedTo": {
>                 "username": "username-of-assignee",
>                 "userID": 1,
>                 "userProjectID": 1
>            } or null,       
>           "taskLocation": "/api/v1/projects/1/tasks/1",
>      },
>      {
>           "title": "Task 2",
>           "taskID": 2,
>           "priority": "High",
>           "dueDate": "2024-08-08",
>           "description": "This is another task!",
>           "comments": 2,
>           "column": {
>                 "columnTitle": "Column title",
>                 "columnID": 1,
>                 "columnIndex": 1,
>                 "columnLocation": "/api/v1/projects/1/columns/1"
>            },
>           "assignedTo": {
>                 "username": "username-of-assignee",
>                 "userID": 1,
>                 "userProjectID": 1
>            } or null,       
>           "taskLocation": "/api/v1/projects/1/tasks/2",
>      },
>     ]
> }
> ```

##### Example cURL

> ```bash
> curl -X GET \
>  https://opm-api.propersi.me/api/v1/projects/1/sprints/1 \
>  -H 'Authorization: Bearer YOUR_JWT_TOKEN' \
> ```

</details>

<details>
 <summary><code>PUT</code> <code><b>/projects/{projectID}/sprints/{sprintID}</b></code> <code>(modifies a sprint in a project)</code>:white_check_mark:</summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `projectID` |  required  | int ($int64) | The unique ID of the project |
> | `sprintID` |  required  | int ($int64) | The unique ID of the sprint |

##### Request Payload

If a field is included, it is assumed that user is trying to edit that field.
Leaving the field out of the payload will keep the field's original value.
No fields can be deleted, or have just empty spaces.

> ```json
> {
>     "startDate": "2023-11-15",
>     "endDate": "2023-11-30",
>     "sprintName": "Sprint Name"
> }
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `{"code":"200","message":"Sprint was modified"}` | Successfully modified the sprint. |
> | `200`         | `application/json`                | `{"code":"200","message":"Sprint was not modified"}` | No modification applied to the sprint. |
> | `400`         | `application/json`                | `{"code":"400","message":"Invalid date range"}` | Invalid date range for sprint. |
> | `400`         | `application/json`                | `{"code":"400","message":"Invalid sprint attributes"}` | Invalid sprint attributes. |
> | `403`         | `application/json`                | `{"code":"403","message":"User not in project, or project does not exist"}` | User not in this project, or project does not exist. |
> | `404`         | `application/json`                | `{"code":"404","message":"Sprint does not exist"}` | Sprint not found. |
> | `409`         | `application/json`                | `{"code":"409","message":"Project contains sprint with that name already"}` | Sprint name must be unique for this project. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "sprintID": 1,
>     "startDate": "2023-11-15",
>     "endDate": "2023-11-30",
>     "sprintName": "Sprint Name"
> }
> ```

##### Example cURL

> ```bash
> curl -X PUT \
>  https://opm-api.propersi.me/api/v1/projects/1/sprints/1 \
>  -H 'Content-Type: application/json' \
>  -H 'Authorization: Bearer YOUR_JWT_TOKEN' \
>  -d '{
>   "sprintName": "Sprint name",
>   "startDate": "2023-11-15",
>   "endDate": "2023-11-30",
>      }' 
> ```
</details>

<details>
 <summary><code>DELETE</code> <code><b>/projects/{projectID}/sprints/{sprintID}</b></code> <code>(deletes a sprint in a project)</code>:white_check_mark:</summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `projectID` |  required  | int ($int64) | The unique ID of the project |
> | `sprintID` |  required  | int ($int64) | The unique ID of the sprint |


##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `{"code":"200","message":"Sprint deleted"}` | Sprint successfully deleted. |
> | `403`         | `application/json`                | `{"code":"403","message":"User not in this project, or project does not exist"}` | User not in this project, or project does not exist. |
> | `404`         | `application/json`                | `{"code":"404","message":"Given sprint does not exist in this project"}` | Sprint not found. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |


##### Example cURL

> ```bash
> curl -X DELETE \
>  https://opm-api.propersi.me/api/v1/projects/1/sprints/1 \
>  -H 'Authorization: Bearer YOUR_JWT_TOKEN' \
> ```
</details>

------------------------------------------------------------------------------------------

#### Team Management

<details>
 <summary><code>GET</code> <code><b>/teams</b></code> <code>(gets all teams associated with a user)</code>:white_check_mark:</summary>

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully retrieved all teams for the user. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "teams": [
>      {
>           "teamID": 1,
>           "teamName": "Team Name 1",
>           "teamLocation": "/api/v1/teams/1",
>           "isTeamCreator": false
>      },
>      {
>           "teamID": 2,
>           "teamName": "Team Name 2",
>           "teamLocation": "/api/v1/teams/2",
>           "isTeamCreator": true
>      },
>     ]
> }
> ```

##### Example cURL

> ```bash
> curl -X GET \
>  https://opm-api.propersi.me/api/v1/teams \
>  -H 'Authorization: Bearer YOUR_JWT_TOKEN' \
> ```

</details>

<details>
 <summary><code>POST</code> <code><b>/teams</b></code> <code>(make a new team)</code>:white_check_mark:</summary>

##### Request Payload

> ```json
> {
>     "teamName": "My new team",
> }
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `201`         | `application/json`                | `See below.` | **Includes a URI to the team resource in the Location Header** |
> | `400`         | `application/json`                | `{"code":"400","message":"You have already made a team with this name"}` | Users must make unique teams. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "teamName": "Team Name 1",
>     "teamID": 1,
>     "teamCreator": 1,
>     "teamLocation": "/api/v1/teams/1",
> }
> ```

##### Example cURL

> ```bash
> curl -X POST \
>  https://opm-api.propersi.me/api/v1/teams \
>  -H 'Content-Type: application/json' \
>  -H 'Authorization: Bearer YOUR_JWT_TOKEN' \
>  -d '{"teamName":"my_username"}' 
> ```

</details>

<details>
 <summary><code>GET</code> <code><b>/teams/{teamID}</b></code> <code>(get all projects associated with a team)</code>:white_check_mark:</summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `teamID` |  required  | int ($int64) | The unique ID of the team |

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Gets all projects associated with a team. |
> | `404`         | `application/json`                | `{"code":"404","message":"User not in team, or does not exist"}` | User not in team, or team does not exist. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "teamID": 1,
>     "teamName": "Team Name 1",
>     "teamLocation": "/api/v1/teams/1
>     "projects": [
>       {
>           "projectName": "project1",
>           "projectID": 1,
>           "lastUpdated": "2023-10-31T15:45:00Z",
>           "projectLocation": "/api/v1/projects/1",
>       },
>       {
>           "projectName": "project2",
>           "projectID": 2,
>           "lastUpdated": "2023-10-31T15:45:00Z",
>           "projectLocation": "/api/v1/projects/2",
>       } 
>     ]
> }
> ```

##### Example cURL

> ```bash
> curl -X GET \
>  https://opm-api.propersi.me/api/v1/teams/1 \
>  -H 'Authorization: Bearer YOUR_JWT_TOKEN' \
> ```

</details>

<details>
 <summary><code>DELETE</code> <code><b>/teams/{teamID}</b></code> <code>(delete a team)</code>:white_check_mark:</summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `teamID` |  required  | int ($int64) | The unique ID of the team |

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `{"code":"200","message":"Team deleted"}` | Team deleted. |
> | `403`         | `application/json`                | `{"code":"403","message":"Team still has associated projects - remove them before deleting the team"}` | Teams must have no associated projects. |
> | `403`         | `application/json`                | `{"code":"403","message":"Team still contains other members - remove them before deleting the team"}` | Teams must have no other members. |
> | `403`         | `application/json`                | `{"code":"403", "message":"User not creator of this team"}` | User not creator - only creator can delete team. |
> | `404`         | `application/json`                | `{"code":"404", "message":"Team does not exist"}` | Team does not exist. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

##### Example cURL

> ```bash
> curl -X DELETE \
>  https://opm-api.propersi.me/api/v1/teams/1 \
>  -H 'Authorization: Bearer YOUR_JWT_TOKEN' \
> ```

</details>

<details>
 <summary><code>GET</code> <code><b>/teams/{teamID}/members</b></code> <code>(get all members associated with a team)</code>:white_check_mark:</summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `teamID` |  required  | int ($int64) | The unique ID of the team |

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Gets all members associated with a team. |
> | `404`         | `application/json`                | `{"code":"404","message":"User not in team, or team does not exist"}` | User not in team, or team does not exist. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "teamID": 1,
>     "teamName": "Team Name 1",
>     "members": [
>       {
>           "username": "user1",
>           "userID": 1,
>           "isTeamCreator": true
>       },
>       {
>           "username": "user2",
>           "userID": 2,
>           "isTeamCreator": false 
>       } 
>     ],
>     "teamLocation": "/api/v1/teams/1"
> }
> ```

##### Example cURL

> ```bash
> curl -X GET \
>  https://opm-api.propersi.me/api/v1/teams/1/members \
>  -H 'Authorization: Bearer YOUR_JWT_TOKEN' \
> ```

</details>

<details>
 <summary><code>POST</code> <code><b>/teams/{teamID}/members</b></code> <code>(add team member to a team)</code>:white_check_mark:</summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `teamID` |  required  | int ($int64) | The unique ID of the team |

##### Request Payload

> ```json
> {
>   "username": "username-here"
> }
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | **Includes a URI to the team resource in the Location Header** |
> | `400`         | `application/json`                | `{"code":"400","message":"User already exists in this team"}` | User already in team. |
> | `404`         | `application/json`                | `{"code":"404","message":"User does not exist"}` | User to add does not exist. |
> | `404`         | `application/json`                | `{"code":"404","message":"User not in team, or team does not exist"}` | User not in team, or team does not exist. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "code": 200,
>     "message": "User added",
> }
> ```

##### Example cURL

> ```bash
> curl -X POST \
>  https://opm-api.propersi.me/api/v1/teams/1/members \
>  -H 'Content-Type: application/json' \
>  -H 'Authorization: Bearer YOUR_JWT_TOKEN' \
>  -d '{"username":"my_username"}' 
> ```

</details>

<details>
 <summary><code>DELETE</code> <code><b>/teams/{teamID}/members/{memberID}</b></code> <code>(remove team member from team)</code>:white_check_mark:</summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `teamID` |  required  | int ($int64) | The unique ID of the team |
> | `memberID` |  required  | int ($int64) | The unique ID of the user |

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `{"code":"200","message":"User removed"}` | Successfully removed user from team. |
> | `403`         | `application/json`                | `{"code":"403","message":"Not authorized"}` | User not in team. |
> | `404`         | `application/json`                | `{"code":"404","message":"User to add does not exist, or is not in team"}` | User to remove does not exist, or not in team. |
> | `404`         | `application/json`                | `{"code":"404","message":"Team does not exist"}` | Team does not exist. |
> | `405`         | `text/html;charset=utf-8`         | None | Invalid HTTP method. |

##### Example cURL

> ```bash
> curl -X DELETE \
>  https://opm-api.propersi.me/api/v1/teams/1/members/1 \
>  -H 'Authorization: Bearer YOUR_JWT_TOKEN' \
> ```

</details>

------------------------------------------------------------------------------------------

