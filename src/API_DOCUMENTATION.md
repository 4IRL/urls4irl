## URLS4IRL Backend API Documentation

- Adopted from: https://stubby4j.com/docs/admin_portal.html
- Inspired by Swagger API docs style & structure: https://petstore.swagger.io/#/pet

------------------------------------------------------------------------------------------

### Authentication

All HTTP requests to the API must include a `session` cookie under the header `Cookie`. Containing a cookie that is expired or invalid
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
>  https://urls4irl.app/home \
>  -H 'Cookie: YOUR_COOKIE' \
> ```

</details>
<details>
 <summary><code>GET</code> <code><b>/utub/[int:UTubID]</b></code> <code>(get specific UTub information)</code></summary>

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
>             "urlString": "https://urls4irl.app",
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
>  https://urls4irl.app/utub/1 \
>  -H 'Cookie: YOUR_COOKIE' \
>  -H 'X-Requested-With: XMLHTTPRequest' \
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
> [
>     {
>         "id": 1,
>         "name": "utub2",
>         "memberRole": "creator",
>     },
>     {
>         "id": 2,
>         "name": "utub1",
>         "memberRole": "member",
>     }
> ]
> ```

##### Example cURL

> ```bash
> curl -X GET \
>  https://urls4irl.app/utubs \
>  -H 'Cookie: YOUR_COOKIE' \
>  -H 'X-Requested-With: XMLHTTPRequest' \
> ```

</details>

<details>
 <summary><code>POST</code> <code><b>/utubs</b></code> <code>(create a new UTub)</code></summary>

##### Request Payload

Payload content-type should be `application/x-www-form-urlencoded; charset=utf−8`.

Required form data:
> ```
> utubName: %NewUTubName%
> utubDescription: %UTubDescription%
> csrf_token: %csrf_token%
> ```

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

###### 400 HTTP Code Response Body - Example

Invalid form data sent with the request.

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
>  https://urls4irl.app/utubs \
>  -H 'Content-Type: application/x-www-form-urlencoded' \
>  -H 'Cookie: YOUR_COOKIE' \
>  --data-urlencode 'utubName=UTub Name'
>  --data-urlencode 'utubDescription=UTub Description'
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
 <summary><code>PATCH</code> <code><b>/utubs/{UTubID}/name</b></code> <code>(update a UTub name)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `UTubID` |  required  | int ($int64) | The unique ID of the UTub to update |

##### Request Payload

Payload content-type should be `application/x-www-form-urlencoded; charset=utf−8`.

Required form data:
> ```
> utubName: %NewUTubName%
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
> }
> ```

###### 400 HTTP Code Response Body - Example

Invalid form data sent with the request.

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
 <summary><code>PATCH</code> <code><b>/utubs/{UTubID}/description</b></code> <code>(update a UTub description)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `UTubID` |  required  | int ($int64) | The unique ID of the UTub to update |

##### Request Payload

Payload content-type should be `application/x-www-form-urlencoded; charset=utf−8`.

Required form data:
> ```
> utubDescription: %NewUTubDescription%
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
>     "utubDescription": "My first UTub"
> }
> ```

###### 400 HTTP Code Response Body - Example

Indicates a missing form field in the payload content.

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to modify UTub description.",
>     "errorCode": 2,
> }
> ```

###### 400 HTTP Code Response Body

Invalid form data sent with the request.

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

Indicates missing or invalid form data sent with the request.

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
>  https://urls4irl.app/utubs/1/urls/2 \
>  -H 'Cookie: YOUR_COOKIE' \
>  -H 'X-Requested-With: XMLHTTPRequest' \
> ```

</details>
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
> | `400`         | `application/json`                | `See below.` | URL unable to be validated, or form errors. |
> | `403`         | `application/json`                | `See below.` | Requesting user not in the requested UTub. |
> | `404`         | `application/json`                | `See below.` | Unable to process the form. |
> | `404`         | `text/html;charset=utf−8`         | None | Unable to find requested UTub. |
> | `405`         | `text/html;charset=utf−8`         | None | Invalid HTTP method. |
> | `409`         | `application/json`                | `See below.` | URL already in UTub. |
> | `429`         | `application/json`                | `See below.` | Too many requests to the Wayback Machine in one minute. |

###### 200 HTTP Code Response Body

> ```json
> {
>     "status": "Success",
>     "message": "New URL created and added to UTub." or "URL added to UTub.",
>     "utubID": 1,
>     "addedByUserID": 1, 
>     "URL": {
>         "urlString": "https://urls4irl.app/",
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

###### 429 HTTP Code Response Body

A 429 might also be given in the response if the user performs too many requests from their own browser.
The following 429 example indicates when all users have attempted to provide URLs that require validation
through the Wayback Machine, which implements its own rate limiting system.

> ```json
> {
>     "status": "Failure",
>     "message": "Too many attempts, please try again in a minute.",
>     "errorCode": 6,
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
>         "urlString": "https://urls4irl.app/",
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
>  https://urls4irl.app/utubs/1/urls/1 \
>  -H 'Cookie: YOUR_COOKIE' \
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
> | `409`         | `application/json`                | `See below.` | URL already in UTub. |
> | `429`         | `application/json`                | `See below.` | Too many requests to the Wayback Machine in one minute. |

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

Indicates missing or invalid form data sent in the request.

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

###### 429 HTTP Code Response Body

A 429 might also be given in the response if the user performs too many requests from their own browser.
The following 429 example indicates when all users have attempted to provide URLs that require validation
through the Wayback Machine, which implements its own rate limiting system.

> ```json
> {
>     "status": "Failure",
>     "message": "Too many attempts, please try again in a minute.",
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
>  --data-urlencode 'csrf_token=CSRF_TOKEN'
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

Indicates missing form data sent in the request.

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

Indicates invalid form data sent in the request.

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
 <summary><code>POST</code> <code><b>/utubs/{UTubID}/tags</b></code> <code>(add a tag to a UTub)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `UTubID` |  required  | int ($int64) | The unique ID of the UTub to add tag to |

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
> | `200`         | `application/json`                | `See below.` | Successfully added a tag to UTub. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `400`         | `application/json`                | `See below.` | Form errors on creation of new string. |
> | `403`         | `application/json`                | `See below.` | Requesting user not in the UTub. |
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
>     }
> }
> ```

###### 400 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "UTub already contains this tag.",
>     "errorCode": 2,
> }
> ```

###### 400 HTTP Code Response Body

Indicates form errors with adding this tag to this UTub.

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to add tag to UTub.",
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
>     "message": "Unable to add tag to UTub.",
>     "errorCode": 1,
> }
> ```

###### 404 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Unable to add tag to UTub.",
>     "errorCode": 4,
> }
> ```

##### Example cURL

> ```bash
> curl -X POST \
>  https://urls4irl.app/utubs/1/tags \
>  -H 'Content-Type: application/x-www-form-urlencoded' \
>  -H 'Cookie: YOUR_COOKIE' \
>  --data-urlencode 'tagString=Hello'
>  --data-urlencode 'csrf_token=CSRF_TOKEN'
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
> | `403`         | `application/json`                | `See below.` | Requesting user not in the UTub. |
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
>     "urlIDs": [1, 2, 3]       // IDs of UTubURLs this tag was removed from, can be empty
> }
> ```

###### 403 HTTP Code Response Body

> ```json
> {
>     "status": "Failure",
>     "message": "Only UTub members can delete tags.",
> }
> ```

##### Example cURL

> ```bash
> curl -X DELETE \
>  https://urls4irl.app/utubs/1/tags/1 \
>  -H 'Content-Type: application/x-www-form-urlencoded' \
>  -H 'Cookie: YOUR_COOKIE' \
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

Payload content-type should be `application/x-www-form-urlencoded; charset=utf−8`.

Required form data:
> ```
> tagString: %Tag Here%
> csrf_token: %csrf_token%
> ```

##### Responses

> | http code     | content-type                      | response  | details |
> |---------------|-----------------------------------|-----------|---------------------------------------------------------|
> | `200`         | `application/json`                | `See below.` | Successfully added a tag to a URL to a UTub. |
> | `302`         | `text/html;charset=utf−8`         | `Redirects and renders HTML for splash page.` | User not email authenticated or not logged in. |
> | `400`         | `application/json`                | `See below.` | URL already contains five tags, or form errors. |
> | `403`         | `application/json`                | `See below.` | Requesting user not in the UTub containing the URL or tag. |
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

Indicates form errors with adding this tag onto this URL in this UTub.

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
 <summary><code>DELETE</code> <code><b>/utubs/{UTubID}/urls/{utubUrlID}/tags/{tagID}</b></code> <code>(remove a tag from a URL in a UTub)</code></summary>

##### Parameters

> | name   |  type      | data type      | description                                          |
> |--------|------------|----------------|------------------------------------------------------|
> | `UTubID` |  required  | int ($int64) | The unique ID of the UTub containing the URL |
> | `utubUrlID` |  required  | int ($int64) | The unique ID of the UTub-URL with the tag to remove |
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
>     "utubUrlTagIDs": [1, 2, 3],         // Contains tag ID array of tags still on URL
>     "utubTag": {
>         "utubTagID": 4,
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
> | `utubUrlID` |  required  | int ($int64) | The unique ID of the UTub-URL associated with the tag to modify |
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

Possible messages include: `Tag on this URL modified.`, `Tag was not modified on this URL.`

> ```json
> {
>     "status": "Success",
>     "message": "Tag on this URL modified.", 
>     "urlTagIDs": [1, 2, 3, 4],      // If modified, contains newly modified tag ID
>     "tag": {
>         "tagID": 4,
>         "tagString": "Hello",
>     },
>     "previousTag": {
>         "tagID": 5,
>         "tagInUTub": false,
>     }
> }
> ```

###### 200 HTTP Code Response Body

> ```json
> {
>     "status": "No change",
>     "message": "Tag was not modified on this URL.",
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

`tagString` field must be included in form.

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
