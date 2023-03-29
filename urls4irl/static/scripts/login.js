// General UI Interactions

$(document).ready(function () {

    // Dev tracking of click-triggered objects
    $(document).click(function (e) {
        console.log($(e.target)[0])
    });

    // CSRF token initialization for non-modal POST requests
    let csrftoken = $('meta[name=csrf-token]').attr('content');
    $.ajaxSetup({
        beforeSend: function (xhr, settings) {
            if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", csrftoken);
            }
        }
    });

});

// General Functions

// Function 1 description
function function1(handle) {

}

// Once valid data is received from the user, this function processes it and attempts a POST request
function createNewUser(e, handle) {
    console.log("postData initiated")
    let postURL; let data;

    postURL = '/user/new';
    data = { name: newUserName }

    let request = $.ajax({
        type: 'post',
        url: postURL,
        data: data
    });

    request.done(function (response, textStatus, xhr) {

        if (xhr.status == 200) {
            createUTub(response.UTub_ID, response.UTub_name)
        }

    })

    request.fail(function (xhr, textStatus, error) {

        if (xhr.status == 404) {
            // Reroute to custom U4I 404 error page
        } else {
            console.log('Unimplemented')
        }
    })
}

// Text input template
function buildInput() {
    
    const parent = $('#') //container

    // New input text field
    let wrapper = document.createElement('div');
    let input = document.createElement('input');
    let submit = document.createElement('i');

    $(wrapper).attr({
        'style': 'display: none'
    })

    $(input).attr({
        'type': 'text',
        'id': 'createUTub',
        'class': 'userInput',
        'placeholder': 'New UTub name',
        'onblur': 'postData(event, "createUTub")'
    })

    $(submit).attr({ 'class': 'fa fa-check-square fa-2x text-success mx-1' })

    wrapper.append(input);
    wrapper.append(submit);
    parent.append(wrapper); 
}