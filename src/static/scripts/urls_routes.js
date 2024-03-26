/* Add URL */

// Displays new URL input prompt
function addURLHideInput() {
    hideInput("addURL");
}

// Displays new URL input prompt
function addURLShowInput() {
    showInput("addURL");
    highlightInput($("#newURLTitle"));
}

// Handles addition of new URL after user submission
function addURL() {
    // Extract data to submit in POST request
    [postURL, data] = addURLSetup();

    AJAXCall("post", postURL, data);

    // Handle response
    request.done(function (response, textStatus, xhr) {
        console.log("success");

        if (xhr.status == 200) {
            addURLSuccess(response);
        }
    });

    request.fail(function (response, textStatus, xhr) {
        console.log("failed");

        if (xhr.status == 404) {
            // Reroute to custom U4I 404 error page
        } else {
            addURLFailure(response);
        }
    });
}

// Prepares post request inputs for addition of a new URL
function addURLSetup() {
    // Assemble post request route
    let postURL = routes.addURL(getActiveUTubID());

    // Assemble submission data
    let newURLTitle = $("#newURLTitle").val();
    let newURL = $("#newURLString").val();
    data = {
        url_string: newURL,
        url_title: newURLTitle,
    };

    return [postURL, data];
}

// Displays changes related to a successful addition of a new URL
function addURLSuccess(response) {
    resetNewURLForm();

    // DP 09/17 need to implement ability to addTagtoURL interstitially before addURL is completed
    let URLcol = createURLBlock(
        response.URL.url_ID,
        response.URL.url_string,
        response.URL.url_title,
        [],
        [],
    );

    $("#URLFocusRow").append(URLcol);

    displayState1URLDeck();
}

// Displays appropriate prompts and options to user following a failed addition of a new URL
function addURLFailure(response) {
    console.log(response);
    console.log("Basic implementation. Needs revision");
    console.log(response.responseJSON.Error_code);
    console.log(response.responseJSON.Message);
    // DP 09/17 could we maybe have a more descriptive reason for failure sent from backend to display to user?
    // Currently STD_JSON.MESSAGE: URL_FAILURE.UNABLE_TO_ADD_URL is too generic. the # * comments are ideal
}

/* Edit URL */

// Shows edit URL inputs
function editURLShowInput() {
    // Show edit submission button, hide other buttons
    let selectedCardDiv = $(getSelectedURLCard());
    let URLOptionsDiv = selectedCardDiv.find(".URLOptions");
    showIfHidden(URLOptionsDiv.find(".submitEditURLBtn"));
    showIfHidden(URLOptionsDiv.find(".cancelEditURLBtn"));
    hideIfShown(URLOptionsDiv.find(".editURLBtn"));
    hideIfShown(URLOptionsDiv.find(".addTagBtn"));
    hideIfShown(URLOptionsDiv.find(".delURLBtn"));

    // Hide access URL button
    hideIfShown(URLOptionsDiv.find(".accessURLBtn"));

    // Show input fields
    let inputElURLString = selectedCardDiv.find(".editURLString");
    let inputDivURLString = inputElURLString.closest(".createDiv");
    showIfHidden($(inputDivURLString));

    // Hide published values
    let URLInfoDiv = selectedCardDiv.find(".URLInfo");
    hideIfShown($(URLInfoDiv.find("h5")));
    hideIfShown($(URLInfoDiv.find("p")));

    // Inhibit selection toggle behavior until user cancels edit, or successfully submits edit. User can still select and edit other URLs in UTub
    unbindSelectURLBehavior();
}

// Hides edit URL inputs
function editURLHideInput() {
    // Hide edit submission button, show other buttons
    let selectedCardDiv = $(getSelectedURLCard());
    let URLOptionsDiv = selectedCardDiv.find(".URLOptions");
    hideIfShown(URLOptionsDiv.find(".submitEditURLBtn"));
    hideIfShown(URLOptionsDiv.find(".cancelEditURLBtn"));
    showIfHidden(URLOptionsDiv.find(".editURLBtn"));
    showIfHidden(URLOptionsDiv.find(".addTagBtn"));
    showIfHidden(URLOptionsDiv.find(".remURLBtn"));

    // Show access URL button
    showIfHidden(URLOptionsDiv.find(".accessURLBtn"));

    // Hide input fields
    let inputElURLString = selectedCardDiv.find(".editURLString");
    let inputDivURLString = inputElURLString.closest(".createDiv");
    hideIfShown(inputDivURLString);

    // Show published values
    let URLInfoDiv = inputElURLString.closest(".URLInfo");
    showIfHidden(URLInfoDiv.find("h5"));
    showIfHidden(URLInfoDiv.find("p"));

    // Update URL options display
    hideIfShown(selectedCardDiv.find(".submitEditURLBtn"));
    showIfHidden(selectedCardDiv.find(".editURLBtn"));
}

// Handles edition of an existing URL
function editURL() {
    // Extract data to submit in POST request
    [postURL, data] = editURLSetup();

    AJAXCall("post", postURL, data);

    // Handle response
    request.done(function (response, textStatus, xhr) {
        console.log("success");

        if (xhr.status == 200) {
            editURLSuccess(response);
        }
    });

    request.fail(function (response, textStatus, xhr) {
        console.log("failed");

        if (xhr.status == 404) {
            // Reroute to custom U4I 404 error page
        } else {
            editURLFail(response);
        }
    });
}

// Prepares post request inputs for edition of a URL
function editURLSetup() {
    let postURL = routes.editURL(getActiveUTubID(), getSelectedURLID());

    let selectedCardDiv = $(getSelectedURLCard());
    let editedURLfield = selectedCardDiv.find(".editURLString")[0];
    let editedURL = editedURLfield.value;
    let editedURLTitlefield = selectedCardDiv.find(".editURLTitle")[0];
    let editedURLTitle = editedURLTitlefield.value;
    console.log(editedURLTitle);
    data = {
        url_string: editedURL,
        url_title: editedURLTitle,
    };

    return [postURL, data];
}

// Displays changes related to a successful edition of a URL
function editURLSuccess(response) {
    // Extract response data
    let editedURLID = response.URL.url_ID;
    let editedURLTitle = response.URL.url_title;
    let editedURLString = response.URL.url_string;
    console.log(response);
    console.log(response.URL);
    console.log(editedURLTitle);

    // If edit URL action, rebind the ability to select/deselect URL by clicking it
    rebindSelectBehavior(editedURLID);

    const selectedCardDiv = $(".selectedURL");

    // Update URL ID
    selectedCardDiv.attr("urlid", editedURLID);

    // Updating input field placeholders
    let editURLTitleInput = selectedCardDiv.find(".editURLTitle");
    editURLTitleInput.text(editedURLTitle);
    let editURLStringInput = selectedCardDiv.find(".editURLString");
    editURLStringInput.text(editedURLString);

    // Update URL body with latest published data
    let URLTitleField = selectedCardDiv.find(".URLTitle");
    URLTitleField.text(editedURLTitle);
    let URLStringField = selectedCardDiv.find(".URLString");
    URLStringField.text(editedURLString);

    // Update URL options
    selectedCardDiv
        .find(".accessURL")
        .off("click")
        .on("click", function (e) {
            e.stopPropagation();
            e.preventDefault();
            accessLink(editedURLString);
        });

    editURLHideInput();
}

// Displays appropriate prompts and options to user following a failed edition of a URL
function editURLFail(response) {
    console.log("Error: Could not edit URL");
    console.log(
        "Failure. Error code: " +
        response.responseJSON.Error_code +
        ". Status: " +
        response.responseJSON.Message,
    );
}

/* Edit URL Title */

// Shows edit URL inputs
function editURLTitleShowInput() {
    // Show edit submission button, hide other buttons
    let selectedCardDiv = $(getSelectedURLCard());
    let URLOptionsDiv = selectedCardDiv.find(".URLOptions");
    showIfHidden(URLOptionsDiv.find(".submitEditURLBtn"));
    showIfHidden(URLOptionsDiv.find(".cancelEditURLBtn"));
    hideIfShown(URLOptionsDiv.find(".editURLBtn"));
    hideIfShown(URLOptionsDiv.find(".addTagBtn"));
    hideIfShown(URLOptionsDiv.find(".remURLBtn"));

    // Hide access URL button
    hideIfShown(URLOptionsDiv.find(".accessURLBtn"));

    // Show input fields
    let inputElURLString = selectedCardDiv.find(".editURLString");
    let inputDivURLString = inputElURLString.closest(".createDiv");
    showIfHidden($(inputDivURLString));

    // Hide published values
    let URLInfoDiv = selectedCardDiv.find(".URLInfo");
    hideIfShown($(URLInfoDiv.find("h5")));
    hideIfShown($(URLInfoDiv.find("p")));

    // Inhibit selection toggle behavior until user cancels edit, or successfully submits edit. User can still select and edit other URLs in UTub
    unbindSelectURLBehavior();
}

// Hides edit URL inputs
function editURLTitleHideInput() {
    // Hide edit submission button, show other buttons
    let selectedCardDiv = $(getSelectedURLCard());
    let URLOptionsDiv = selectedCardDiv.find(".URLOptions");
    hideIfShown(URLOptionsDiv.find(".submitEditURLBtn"));
    hideIfShown(URLOptionsDiv.find(".cancelEditURLBtn"));
    showIfHidden(URLOptionsDiv.find(".editURLBtn"));
    showIfHidden(URLOptionsDiv.find(".addTagBtn"));
    showIfHidden(URLOptionsDiv.find(".remURLBtn"));

    // Show access URL button
    showIfHidden(URLOptionsDiv.find(".accessURLBtn"));

    // Hide input fields
    let inputElURLString = selectedCardDiv.find(".editURLString");
    let inputDivURLString = inputElURLString.closest(".createDiv");
    hideIfShown(inputDivURLString);

    // Show published values
    let URLInfoDiv = inputElURLString.closest(".URLInfo");
    showIfHidden(URLInfoDiv.find("h5"));
    showIfHidden(URLInfoDiv.find("p"));

    // Update URL options display
    hideIfShown(selectedCardDiv.find(".submitEditURLBtn"));
    showIfHidden(selectedCardDiv.find(".editURLBtn"));
}

// Handles edition of an existing URL
function editURLTitle() {
    // Extract data to submit in POST request
    [postURL, data] = editURLSetup();

    AJAXCall("post", postURL, data);

    // Handle response
    request.done(function (response, textStatus, xhr) {
        console.log("success");

        if (xhr.status == 200) {
            editURLSuccess(response);
        }
    });

    request.fail(function (response, textStatus, xhr) {
        console.log("failed");

        if (xhr.status == 404) {
            // Reroute to custom U4I 404 error page
        } else {
            editURLFail(response);
        }
    });
}

// Prepares post request inputs for edition of a URL
function editURLTitleSetup() {
    let postURL = routes.editURL(getActiveUTubID(), getSelectedURLID());

    let selectedCardDiv = $(getSelectedURLCard());
    let editedURLfield = selectedCardDiv.find(".editURLString")[0];
    let editedURL = editedURLfield.value;
    let editedURLTitlefield = selectedCardDiv.find(".editURLTitle")[0];
    let editedURLTitle = editedURLTitlefield.value;
    console.log(editedURLTitle);
    data = {
        url_string: editedURL,
        url_title: editedURLTitle,
    };

    return [postURL, data];
}

// Displays changes related to a successful edition of a URL
function editURLTitleSuccess(response) {
    // Extract response data
    let editedURLID = response.URL.url_ID;
    let editedURLTitle = response.URL.url_title;
    let editedURLString = response.URL.url_string;
    console.log(response);
    console.log(response.URL);
    console.log(editedURLTitle);

    // If edit URL action, rebind the ability to select/deselect URL by clicking it
    rebindSelectBehavior(editedURLID);

    const selectedCardDiv = $(".selectedURL");

    // Update URL ID
    selectedCardDiv.attr("urlid", editedURLID);

    // Updating input field placeholders
    let editURLTitleInput = selectedCardDiv.find(".editURLTitle");
    editURLTitleInput.text(editedURLTitle);
    let editURLStringInput = selectedCardDiv.find(".editURLString");
    editURLStringInput.text(editedURLString);

    // Update URL body with latest published data
    let URLTitleField = selectedCardDiv.find(".URLTitle");
    URLTitleField.text(editedURLTitle);
    let URLStringField = selectedCardDiv.find(".URLString");
    URLStringField.text(editedURLString);

    // Update URL options
    selectedCardDiv
        .find(".accessURL")
        .off("click")
        .on("click", function (e) {
            e.stopPropagation();
            e.preventDefault();
            accessLink(editedURLString);
        });

    editURLHideInput();
}

// Displays appropriate prompts and options to user following a failed edition of a URL
function editURLTitleFail(response) {
    console.log("Error: Could not edit URL");
    console.log(
        "Failure. Error code: " +
        response.responseJSON.Error_code +
        ". Status: " +
        response.responseJSON.Message,
    );
}

/* Delete URL */

// Hide confirmation modal for removal of the selected URL
function deleteURLHideModal() {
    $("#confirmModal").modal("hide");
    unbindEnter();
}

// Show confirmation modal for removal of the selected existing URL from current UTub
function deleteURLShowModal() {
    let modalTitle = "Are you sure you want to delete this URL from the UTub?";
    let buttonTextDismiss = "Just kidding";
    let buttonTextSubmit = "Delete URL";

    $("#confirmModalTitle").text(modalTitle);

    $("#modalDismiss")
        .off("click")
        .on("click", function (e) {
            e.preventDefault();
            removeURLHideModal();
        })
        .text(buttonTextDismiss);
    // Esc key cancels operation
    bindKeyToFunction(removeURLHideModal, 27);

    $("#modalSubmit")
        .off("click")
        .on("click", function (e) {
            e.preventDefault();
            removeURL();
        })
        .text(buttonTextSubmit);
    // Enter key sends operation
    bindKeyToFunction(removeURL, 13);

    $("#confirmModal").modal("show");

    hideIfShown($("#modalRedirect"));
}

// Handles post request and response for removing an existing URL from current UTub, after confirmation
function deleteURL() {
    // Extract data to submit in POST request
    postURL = deleteURLSetup();

    let request = AJAXCall("post", postURL, []);

    // Handle response
    request.done(function (response, textStatus, xhr) {
        console.log("success");

        if (xhr.status == 200) {
            deleteURLSuccess();
        }
    });

    request.fail(function (response, textStatus, xhr) {
        console.log("failed");

        if (xhr.status == 404) {
            // Reroute to custom U4I 404 error page
        } else {
            removeURLFail(response);
        }
    });
}

// Prepares post request inputs for removal of a URL
function deleteURLSetup() {
    let postURL = routes.deleteURL(getActiveUTubID(), getSelectedURLID());

    return postURL;
}

// Displays changes related to a successful removal of a URL
function deleteURLSuccess() {
    // Close modal
    $("#confirmModal").modal("hide");

    let cardCol = $("div[urlid=" + getSelectedURLID() + "]").closest(".cardCol");
    cardCol.fadeOut();
    cardCol.remove();

    displayState1URLDeck();
}

// Displays appropriate prompts and options to user following a failed removal of a URL
function deleteURLFail(xhr, textStatus, error) {
    console.log("Error: Could not delete URL");

    if (xhr.status == 409) {
        console.log(
            "Failure. Status code: " + xhr.status + ". Status: " + textStatus,
        );
        console.log("Error: " + error.Error_code);
    }
}  