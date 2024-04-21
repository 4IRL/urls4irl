## URLS4IRL Backend API Documentation

- Adopted from: https://stubby4j.com/docs/admin_portal.html
- Inspired by Swagger API docs style & structure: https://petstore.swagger.io/#/pet

------------------------------------------------------------------------------------------

### Authentication

All HTTP requests to the API must include a session cookie under the header `Cookie`. Containing a cookie that is expired or invalid
will redirect the user to the splash page. HTTP requests made over AJAX that use form data require a CSRF token via the `X-Csrftoken` header.
Otherwise, HTTP requests containing form data should include a field for `csrf_token`, with the token in the value.

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
>  https://urls4irl.app/ \
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
>  https://urls4irl.app/login \
> ```

</details>

<details>
 <summary><code>POST</code> <code><b>/login</b></code> <code>(logs user in, generates session cookie)</code></summary>

##### Request Payload

Payload content-type should be `application/x-www-form-urlencoded; charset=utf−8`.

Required form data:
> ```
> username: %username%
> password: %password%
> csrf_token: %csrf_token%
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `text/html;charset=utf−8`         | `Provides URL to user home page.` | On successful login, sends user to their home page, and generates a session cookie for them. |
> | `400`         | `application/json`                | `See below.` | Form errors within login form. |
> | `401`         | `application/json`                | `See below.` | User has not email validated. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

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
>  https://urls4irl.app/logout \
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
>  https://urls4irl.app/register \
> ```

</details>

<details>
 <summary><code>POST</code> <code><b>/register</b></code> <code>(register user)</code></summary>

##### Request Payload

Payload content-type should be `application/x-www-form-urlencoded; charset=utf−8`.

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
> | `201`         | `text/html;charset=utf−8`         | `Renders HTML for email validation modal.` | Once a user is registered, they must be email validated. |
> | `400`         | `application/json`                | `See below.` | Form errors within registration form. |
> | `401`         | `application/json`                | `See below.` | User has already created this account but not email validated. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

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
> | `200`         | `text/html;charset=utf−8`         | `Renders HTML for email validation modal.` | Renders the modal to email validate, if user is logged in but not email validated. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User has not made an account to confirm an email for. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects user to the /home page.` | User already logged in and email validated. Redirects user to /home page and renders it. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

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
> | `302`         | `text/html;charset=utf−8`         | `Redirects user to the /home page.` | User already logged in and email validated. Redirects user to /home page and renders it. |
> | `400`         | `application/json`                | `See below.` | Error sending email to given address. |
> | `400`         | `application/json`                | `See below.` | Error with Mailjet service. |
> | `404`         | `text/html;charset=utf−8`         | None | User to send email to does not exist. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |
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
> | `302`         | `text/html;charset=utf−8`         | `Redirects user to the /home page.` | User has been email validated. Redirects user to /home page and renders it. |
> | `400`         | `text/html;charset=utf−8`         | `Renders splash page and email validation modal.` | Token expired. Token has been reset. |
> | `404`         | `text/html;charset=utf−8`         | None | Email validation or user for this token does not exist. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

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
> | `200`         | `text/html;charset=utf−8`         | `Renders forgot-password modal.` | Displays the forgot password modal to the user. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User has not validated their email. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects user to the /home page.` | User already logged in and email validated. Redirects user to /home page and renders it. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

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

Payload content-type should be `application/x-www-form-urlencoded; charset=utf−8`.

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
> | `200`         | `text/html;charset=utf−8`         | `Renders reset-password modal.` | Displays the reset password modal to the user. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | Token expired. |
> | `404`         | `text/html;charset=utf−8`         | None | Invalid token, invalid user, user not email authenticated. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

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

Payload content-type should be `application/x-www-form-urlencoded; charset=utf−8`.

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
> | `200`         | `text/html;charset=utf−8`         | `Renders user's home page, with below JSON embedded.` | Displays the user's home page, with selectable UTubs. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `404`         | `text/html;charset=utf−8`         | None | Unknown error occurred. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

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
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `404`         | `text/html;charset=utf−8`         | None | Could not find associated UTub, or user not in requested UTub. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

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
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `400`         | `application/json`                | `See below.` | Form errors in making the new UTub. |
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

Payload content-type should be `application/x-www-form-urlencoded; charset=utf−8`.

Required form data:
> ```
> name: %NewUTubName%
> csrf_token: %csrf_token%
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully modified a UTub name. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `400`         | `application/json`                | `See below.` | Form errors when processing new UTub name. |
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

Payload content-type should be `application/x-www-form-urlencoded; charset=utf−8`.

Required form data:
> ```
> name: %NewUTubName%
> csrf_token: %csrf_token%
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully modified the UTub description. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `400`         | `application/json`                | `See below.` | Form errors when processing new UTub description. |
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

------------------------------------------------------------------------------------------

#### UTub Members

<details>
 <summary><code>POST</code> <code><b>/utubs/{UTubID}/members</b></code> <code>(add a member to a UTub)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `UTubID` |  required  | int ($int64) | The unique ID of the UTub to add a member to |

##### Request Payload

Payload content-type should be `application/x-www-form-urlencoded; charset=utf−8`.

Required form data:
> ```
> username: %newMemberName%
> csrf_token: %csrf_token%
> ```


##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully added a member to the UTub. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `400`         | `application/json`                | `See below.` | Form errors in adding member, or member already in UTub. |
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
>     "utubName": "UTub 1",
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
>  https://urls4irl.app/utubs/1/members \
>  -H 'Content-Type: application/x-www-form-urlencoded' \
>  -H 'Cookie: YOUR_COOKIE' \
>  --data-urlencode 'username=UTub Name'
>  --data-urlencode 'csrf_token=CSRF_TOKEN'
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
>     "utubName": "UTub 1",
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
>  https://urls4irl.app/utubs/1/members/2 \
>  -H 'Cookie: YOUR_COOKIE' \
> ```

</details>

------------------------------------------------------------------------------------------

#### UTub URLs

<details>
 <summary><code>POST</code> <code><b>/utubs/{UTubID}/urls</b></code> <code>(add a URL to a UTub)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `UTubID` |  required  | int ($int64) | The unique ID of the UTub containing the URL |

##### Request Payload

Payload content-type should be `application/x-www-form-urlencoded; charset=utf−8`.

Required form data:
> ```
> urlString: %www.google.com%
> urlTitle: %This is google%
> csrf_token: %csrf_token%
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully added a URL to a UTub. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `400`         | `application/json`                | `See below.` | URL unable to be validated, or already in UTub, or form errors. |
> | `403`         | `application/json`                | `See below.` | Requesting user not in the requested UTub. |
> | `404`         | `application/json`                | `See below.` | Unable to process the form. |
> | `404`         | `text/html;charset=utf−8`         | None | Unable to find requested UTub. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "status": "Success",
>     "message": "New URL created and added to UTub." or "URL added to UTub.",
>     "utubID": 1,
>     "utubName": "UTub 1",
>     "addedBy": 1, 
>     "URL": {
>         "urlString": "https://urls4irl.app/,
>         "urlID": 1,
>         "urlTitle": "This is my home page!",
>     }
> }
> ```

###### 400 HTTP Code Response Body

Indicates the URL could not be validated.

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to add this URL.",
>     "errorCode": 2,
> }
> ```

###### 400 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "URL already in UTub.",
>     "errorCode": 3,
> }
> ```

###### 400 HTTP Code Response Body

Indicates form errors with adding this URL to this UTub.

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

##### Example cURL

> ```bash
> curl -X POST \
>  https://urls4irl.app/utubs/1/urls \
>  -H 'Content-Type: application/x-www-form-urlencoded' \
>  -H 'Cookie: YOUR_COOKIE' \
>  --data-urlencode 'urlString=urls4irl.app'
>  --data-urlencode 'urlTitle=My home page'
>  --data-urlencode 'csrf_token=CSRF_TOKEN'
> ```

</details>
<details>
 <summary><code>DELETE</code> <code><b>/utubs/{UTubID}/urls/{urlID}</b></code> <code>(remove a URL from a UTub)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `UTubID` |  required  | int ($int64) | The unique ID of the UTub containing the URL |
> | `urlID` |  required  | int ($int64) | The unique ID of the URL to remove from the UTub |

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
>     "utubName": "UTub 1",
>     "URL": {
>         "urlString": "https://urls4irl.app/,
>         "urlID": 1,
>         "urlTitle": "This is my home page!",
>     },
>     "urlTags": [1, 2, 3] // Tag IDs associated with the removed URL, in this UTub
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
>  https://urls4irl.app/utubs/1/urls/1 \
>  -H 'Cookie: YOUR_COOKIE' \
> ```

</details>
<details>
 <summary><code>PUT</code> <code><b>/utubs/{UTubID}/urls/1</b></code> <code>(edit URL string and/or title)</code></summary>

###### Note: This route is deprecated in favor of the individual routes to edit the URL or the URL title

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `UTubID` |  required  | int ($int64) | The unique ID of the UTub containing the URL |
> | `urlID` |  required  | int ($int64) | The unique ID of the URL to modify |

##### Request Payload

Payload content-type should be `application/x-www-form-urlencoded; charset=utf−8`.

Required form data:
> ```
> urlString: %www.google.com%
> urlTitle: %New URL Title%     // Can be an empty string to delete it         
> csrf_token: %csrf_token%
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully modified a UTub name. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `400`         | `application/json`                | `See below.` | Missing form fields, or unable to validate URL. |
> | `403`         | `application/json`                | `See below.` | User must be creator of UTub or adder of URL to modify URL. |
> | `404`         | `application/json`                | `See below.` | Unable to process the form. |
> | `404`         | `text/html;charset=utf−8`         | None | Unable to find UTub, or the URL within the UTub. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

Possible messages include: `URL and URL title were not modified.`, `URL title was modified.`

> ```json
> {
>     "status": "Success" or "No change",
>     "message": "URL and/or URL title modified.",
>     "utubID": 1,
>     "utubName": "New UTub Name",
>     "utubDescription": "My first UTub"
> }
> ```

###### 400 HTTP Code Response Body

`urlString` field must not just include whitespace.

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
>     "message": "Unable to modify this URL.",
>     "errorCode": 3,
> }
> ```

###### 400 HTTP Code Response Body

`urlTitle` field must be included in form.

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to update, please check inputs.",
>     "errorCode": 4,
>     "errors": {
>         "urlTitle": ["This field is required."],
>     }
> }
> ```

###### 400 HTTP Code Response Body

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
>     "message": "Unable to modify this URL.",
>     "errorCode": 6,
> }
> ```

##### Example cURL

> ```bash
> curl -X PATCH \
>  https://urls4irl.app/utubs/1/urls/1 \
>  -H 'Content-Type: application/x-www-form-urlencoded' \
>  -H 'Cookie: YOUR_COOKIE' \
>  --data-urlencode 'urlString=www.google.com'
>  --data-urlencode 'urlTitle=Google'
>  --data-urlencode 'csrf_token=CSRF_TOKEN'
> ```

</details>
<details>
 <summary><code>PATCH</code> <code><b>/utubs/{UTubID}/urls/{urlID}</b></code> <code>(edit the URL string in a UTub)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `UTubID` |  required  | int ($int64) | The unique ID of the UTub containing the URL |
> | `urlID` |  required  | int ($int64) | The unique ID of the URL to modify |

##### Request Payload

Payload content-type should be `application/x-www-form-urlencoded; charset=utf−8`.

Required form data:
> ```
> urlString: %New URL String%
> csrf_token: %csrf_token%
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully modified the URL string, or no change. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `400`         | `application/json`                | `See below.` | Form errors, or unable to validate URL. |
> | `403`         | `application/json`                | `See below.` | User must be creator of UTub or adder of URL to modify URL. |
> | `404`         | `application/json`                | `See below.` | Unable to process the form. |
> | `404`         | `text/html;charset=utf−8`         | None | Unable to find UTub, or URL in UTub. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "status": "Success" or "No change",
>     "message": "URL modified." or "URL not modified",
>     "utubID": 1,
>     "utubName": "New UTub Name",
>     "URL": {
>         "urlID": 1,
>         "urlString": "https://www.google.com",
>         "urlTitle": "This is google.",
>         "urlTags": [1, 2, 3],                   // Array of tag IDs associated with this URL in UTub
>         "addedBy": 1,
>     }
> }
> ```

###### 400 HTTP Code Response Body

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
>     "message": "Unable to modify this URL.",
>     "errorCode": 3,
> }
> ```

###### 400 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to update, please check inputs.",
>     "errorCode": 4,
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
>     "errorCode": 5,
> }
> ```

##### Example cURL

> ```bash
> curl -X PATCH \
>  https://urls4irl.app/utubs/1/urls/1 \
>  -H 'Content-Type: application/x-www-form-urlencoded' \
>  -H 'Cookie: YOUR_COOKIE' \
>  --data-urlencode 'urlString=www.google.com'
>  --data-urlencode 'csrf_token=CSRF_TOKEN'
> ```

</details>

<details>
 <summary><code>PATCH</code> <code><b>/utubs/{UTubID}/urls/{urlID}/title</b></code> <code>(edit the title of a URL in a UTub)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `UTubID` |  required  | int ($int64) | The unique ID of the UTub containing the URL |
> | `urlID` |  required  | int ($int64) | The unique ID of the URL with the title to modify |

##### Request Payload

Payload content-type should be `application/x-www-form-urlencoded; charset=utf−8`.

Required form data:
> ```
> urlTitle: %New URL Title%
> csrf_token: %csrf_token%
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully modified the URL title, or no change. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `400`         | `application/json`                | `See below.` | Form errors with modifying URL title. |
> | `403`         | `application/json`                | `See below.` | User must be creator of UTub or adder of URL to modify title of URL. |
> | `404`         | `application/json`                | `See below.` | Unable to process the form. |
> | `404`         | `text/html;charset=utf−8`         | None | Unable to find UTub, or URL in UTub. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "status": "Success" or "No change",
>     "message": "URL title was modified." or "URL title not modified",
>     "utubID": 1,
>     "utubName": "New UTub Name",
>     "URL": {
>         "urlID": 1,
>         "urlString": "https://www.google.com",
>         "urlTitle": "This is google.",
>         "urlTags": [1, 2, 3],                   // Array of tag IDs associated with this URL in UTub
>         "addedBy": 1,
>     }
> }
> ```

###### 400 HTTP Code Response Body

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

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to update, please check inputs.",
>     "errorCode": 3,
>     "errors": {
>         "urlString": ["Field cannot be longer than 140 characters."],
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
>  https://urls4irl.app/utubs/1/urls/1/title \
>  -H 'Content-Type: application/x-www-form-urlencoded' \
>  -H 'Cookie: YOUR_COOKIE' \
>  --data-urlencode 'urlTitle=New URL title'
>  --data-urlencode 'csrf_token=CSRF_TOKEN'
> ```

</details>

------------------------------------------------------------------------------------------

#### UTub Tags

<details>
 <summary><code>POST</code> <code><b>/utubs/{UTubID}/urls/{urlID}/tags</b></code> <code>(add a tag to a URL in a UTub)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `UTubID` |  required  | int ($int64) | The unique ID of the UTub containing the URL |
> | `urlID` |  required  | int ($int64) | The unique ID of the URL to add the tag to |

##### Request Payload

Payload content-type should be `application/x-www-form-urlencoded; charset=utf−8`.

Required form data:
> ```
> tagString: %Tag Here%
> csrf_token: %csrf_token%
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully added a URL to a UTub. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `400`         | `application/json`                | `See below.` | URL already contains five tags, or form errors. |
> | `403`         | `application/json`                | `See below.` | Requesting user not in the UTub containing URL. |
> | `404`         | `application/json`                | `See below.` | Unable to process the form. |
> | `404`         | `text/html;charset=utf−8`         | None | Unable to find requested UTub or given URL in UTub. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "status": "Success",
>     "message": "Tag added to this URL.",
>     "utubID": 1,
>     "utubName": "UTub 1",
>     "urlID": 1,
>     "urlTags": [1, 2, 3, 4],      // Contains newly added tag ID
>     "tag": {
>         "tagID": 4,
>         "tagString": "Hello",
>     }
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

Indicates form errors with adding this URL to this UTub.

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to add tag to URL.",
>     "errorCode": 4,
>     "errors": {
>         "tagString": ["This field is required."],
>     }
> }
> ```

###### 403 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to add tag to URL.",
>     "errorCode": 1,
> }
> ```

###### 404 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to add tag to URL.",
>     "errorCode": 5,
> }
> ```

##### Example cURL

> ```bash
> curl -X POST \
>  https://urls4irl.app/utubs/1/urls/1/tags \
>  -H 'Content-Type: application/x-www-form-urlencoded' \
>  -H 'Cookie: YOUR_COOKIE' \
>  --data-urlencode 'tagString=Hello'
>  --data-urlencode 'csrf_token=CSRF_TOKEN'
> ```

</details>
<details>
 <summary><code>DELETE</code> <code><b>/utubs/{UTubID}/urls/{urlID}/tags/{tagID}</b></code> <code>(remove a tag from a URL from a UTub)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `UTubID` |  required  | int ($int64) | The unique ID of the UTub containing the URL |
> | `urlID` |  required  | int ($int64) | The unique ID of the URL with the tag to remove |
> | `tagID` |  required  | int ($int64) | The unique ID of the tag to remove |

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully removed the tag from the URL in the UTub. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `403`         | `application/json`                | `See below.` | User must be member of UTub to remove a tag from a URL. |
> | `404`         | `text/html;charset=utf−8`         | None | Unable to find UTub, URL in UTub, or tag on URL in UTub. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "status": "Success",
>     "message": "Tag removed from this URL.",
>     "utubID": 1,
>     "utubName": "UTub 1",
>     "urlID": 1,
>     "urlTags": [1, 2, 3],         // Contains tag ID array of tags still on URL
>     "tagInUTub": false            // Indicates if removed tag still exists in UTub
>     "tag": {
>         "tagID": 4,
>         "tagString": "Hello",
>     }
> }
> ```

###### 403 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Only UTub members can remove tags.",
> }
> ```

##### Example cURL

> ```bash
> curl -X DELETE \
>  https://urls4irl.app/utubs/1/urls/1/tags/4 \
>  -H 'Cookie: YOUR_COOKIE' \
> ```

</details>
<details>
 <summary><code>PUT</code> <code><b>/utubs/{UTubID}/urls/1/tags/1</b></code> <code>(modify tag on URL in UTub)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `UTubID` |  required  | int ($int64) | The unique ID of the UTub containing the URL with given tag |
> | `urlID` |  required  | int ($int64) | The unique ID of the URL associated with the tag to modify |
> | `tagID` |  required  | int ($int64) | The unique ID of the tag to modify |

##### Request Payload

Payload content-type should be `application/x-www-form-urlencoded; charset=utf−8`.

Required form data:
> ```
> tagString: %New Tag%
> csrf_token: %csrf_token%
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully modified a tag, or no change. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `400`         | `application/json`                | `See below.` | Missing form fields or tag already on URL. |
> | `403`         | `application/json`                | `See below.` | Only UTub members can modify a tag on a URL. |
> | `404`         | `application/json`                | `See below.` | Unable to process the form. |
> | `404`         | `text/html;charset=utf−8`         | None | Unable to find UTub, the URL within the UTub, or the tag on the URL. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |

###### 200 HTTP Code Response Body

Possible messages include: `URL and URL title were not modified.`, `URL title was modified.`

> ```json
> {
>     "status": "Success" or "No change",
>     "message": "Tag on this URL modified.", or "Tag was not modified on this URL.",
>     "utubID": 1,
>     "utubName": "New UTub Name",
>     "urlID": 1,
>     "urlTags": [1, 2, 3, 4],      // If modified, contains newly modified tag ID
>     "tag": {
>         "tagID": 4,
>         "tagString": "Hello",
>     }
> }
> ```

###### 400 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "URL already has this tag.",
>     "errorCode": 2,
> }
> ```

###### 400 HTTP Code Response Body

`urlTitle` field must be included in form.

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to add tag to URL.",
>     "errorCode": 3,
>     "errors": {
>         "tagString": ["This field is required."],
>     }
> }
> ```

###### 403 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Only UTub members can modify tags.",
>     "errorCode": 1
> }
> ```

###### 404 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to add tag to URL.",
>     "errorCode": 4,
> }
> ```

##### Example cURL

> ```bash
> curl -X PUT \
>  https://urls4irl.app/utubs/1/urls/1/tags/1 \
>  -H 'Content-Type: application/x-www-form-urlencoded' \
>  -H 'Cookie: YOUR_COOKIE' \
>  --data-urlencode 'tagString=NewTag'
>  --data-urlencode 'csrf_token=CSRF_TOKEN'
> ```

</details>

------------------------------------------------------------------------------------------

