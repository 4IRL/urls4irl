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

    // Prevent form refresh of page on submittal
    $('form').on('submit', function () { return false; })

    // Submission of user input data
    $('.activeInput').on('blur', function () {
        console.log("Blur caught")
        let inputEl = $(this);
        console.log(inputEl)
        let handle = inputEl.attr('id');
        console.log(handle)

        if (document.activeElement.localname == 'input') {
            return;
        }

        if (inputEl[0].value) {
            postData(inputEl[0].value, handle)
        } else {
            // Input is empty
        }
        inputEl.hide();
        inputEl.removeClass('active');

    })

    // Trigger blur and submit data
    $(document).on('keyup', function (e) {
        if (e.keyCode === 13) {
            e.preventDefault();
            e.target.blur();
        }
    })

    // Keyboard navigation between selected UTubs or URLs
    $(document).on('keyup', function (e) {
        if ($('#URLFocusRow').length > 0) {     // Some URL is selected
            let keycode = (e.keyCode ? e.keyCode : e.which);
            let prev = keycode == 37 || keycode == 38;
            let next = keycode == 39 || keycode == 40;
            let UPRcards = $('#UPRRow').children('.cardCol').length;
            let LWRcards = $('#LWRRow').children('.cardCol').length;

            if (prev && UPRcards > 0) {              // User wants to highlight previous URL
                let cardCol = $($('#UPRRow').children('.cardCol')[UPRcards - 1]);
                selectURL($(cardCol[0].children).attr('urlid'))
            } else if (next && LWRcards > 0) {       // User wants to highlight next URL
                let cardCol = $($('#LWRRow').children('.cardCol')[0]);
                selectURL($(cardCol[0].children).attr('urlid'))
            } else {
                deselectURL($('url.selected').parent())
            }

        } else {
            let prev = keycode == 38;
            let next = keycode == 40;
        }
    })

    // Navbar animation
    $('.first-button').on('click', function () {

        $('.animated-icon1').toggleClass('open');
    });
    $('.second-button').on('click', function () {

        $('.animated-icon2').toggleClass('open');
    });
    $('.third-button').on('click', function () {

        $('.animated-icon3').toggleClass('open');
    });
});

// General Functions

// Request user text input by placing a text input element in the appropriate location and await valid input
function showInput(handle) {

    let inputEl = $('#' + handle);
    let inputDiv = inputEl.closest('div');

    // Show temporary input text element
    inputDiv.show();
    inputEl.addClass('activeInput');

    inputEl.focus();
    inputEl[0].setSelectionRange(0, inputEl[0].value.length);
}

// Once valid data is received from the user, this function processes it and attempts a POST request
function postData(e, handle) {
    console.log("postData initiated")
    let postURL; let data;

    switch (handle) {
        case 'createUTub':
            postURL = '/utub/new';
            let newUTubName = e.target.value;
            data = { name: newUTubName }
            $(e.target).parent().hide();
            break;
        case 'createURL':
            console.log("createURL attempted")
            postURL = '/url/add/' + currentUTubID();
            let createURLCard = $(e.target).parent().parent();
            let newURL = createURLCard.find('#newURL')[0].value;
            let newURLDescription = createURLCard.find('#newURLDescription')[0].value;
            data = {
                url_string: newURL,
                url_description: newURLDescription
            }
            break;
        case 'createTag':
            postURL = '/tag/new';
            let newTagName = e.target.value;
            data = { name: newTagName }
            $(e.target).parent().hide();
            break;
        case 'editUTubDescription':
            console.log('Unimplemented')
            break;
        case 'editURL':
            postURL = '/url/edit';
            console.log('Unimplemented')
            break;
        case 'editURLDescription':
            console.log('Unimplemented')
            break;
        case 'addTag':
            postURL = '/tag/add/[urlid?]';
            data = { name: userInput }
            break;
        case 'editTags':
            // Send UTubID
        let tagID = e[0];
        let tagText = e[1];
            postURL = '/tag/edit/' + tagID;
            data = {
                id: tagID,
                tag_string: tagText
            }
            break;
        default:
            console.log('Unimplemented')
    }

    let request = $.ajax({
        type: 'post',
        url: postURL,
        data: data
    });

    request.done(function (response, textStatus, xhr) {

        if (xhr.status == 200) {
            switch (handle) {
                case 'createUTub':
                    // Clear form and get ready for new input
                    e.target.value = '';
                    // Deselect current UTub
                    $('.UTub').removeClass('active');
                    $('input[type=radio]').prop('checked', false);

                    createUTub(response.UTub_ID, response.UTub_name)

                    break;
                case 'createURL':
                    // Clear form and get ready for new input
                    let createURLCard = $(e.target).parent().parent();
                    let URLDescription = createURLCard.find('#newURLDescription')[0].value;
                    createURLCard.find('#newURL')[0].value = '';
                    createURLCard.find('#newURLDescription')[0].value = '';

                    let URLID = response.URL.url_ID;

                    let URLcol = createURL(URLID, response.URL.url_string, URLDescription, [], []);
                    $(URLcol).insertAfter('.url.selected');
                    deselectURL($('.url.selected').parent());
                    $('.url.selected').parent().hide();
                    selectURL(URLID);

                    break;
                case 'createTag':
                    console.log('Unimplemented')
                    break;
                case 'editUTubDescription':
                    console.log('Unimplemented')
                    break;
                case 'addTag':
                    console.log('Unimplemented')
                    break;
                case 'editURL':
                    console.log('Unimplemented')
                    break;
                case 'editURLDescription':
                    console.log('Unimplemented')
                    break;
                default:
                    console.log('Unimplemented')
            }
        }
    })

    request.fail(function (xhr, textStatus, error) {

        if (xhr.status == 404) {
            // Reroute to custom U4I 404 error page
        } else {
            switch (handle) {
                case 'createUTub':
                    console.log('Unimplemented')
                    break;
                case 'createURL':
                    console.log('Unimplemented')
                    break;
                case 'createTag':
                    console.log('Unimplemented')
                    break;
                case 'editUTubDescription':
                    console.log('Unimplemented')
                    break;
                case 'addTag':
                    console.log('Unimplemented')
                    break;
                case 'editURL':
                    console.log('Unimplemented')
                    break;
                case 'editURLDescription':
                    console.log('Unimplemented')
                    break;
                default:
                    console.log('Unimplemented')
            }
        }
    })
}

// Creates option dropdown menu of users in RH UTub information panel
function gatherUsers(dictUsers, creator) {
    html = '<option disabled selected value> -- Select a User -- </option>';
    for (let i in dictUsers) {
        let user = dictUsers[i];
        if (user.id == creator) {
            $('#UTubOwner')[0].innerHTML = user.username;
        } else {
            html += '<option value=' + user.id + '>' + user.username + '</option>'
        }
    }
    $('#UTubUsers')[0].innerHTML = html;
}


function cardEdit(selectedUTubID, selectedURLid, infoType) {
    let jQuerySel = "div.url.selected[urlid=" + selectedURLid + "]";    // Find jQuery selector with selected ID
    let inputParent; let initString;
    let inputEl; let inputID;
    let postURL; let originalURL;

    if (infoType == 'tag') {
        inputParent = $(jQuerySel).find('div.URLTags');     // Find appropriate card element
        initString = '';
        inputEl = $('#new_tag');                            // Temporary input text element
        inputID = 'new_tag';
        postURL = '/tag/add/';
    } else {
        inputParent = $(jQuerySel).find('p.card-text');     // Find appropriate card element         
        initString = inputParent[0].innerText;              // Store pre-edit values
        originalURL = inputParent[0].innerText;             // Store pre-edit values
        $(inputParent).html('');                            // Clear url card-text
        inputEl = $('#edit_url');                           // Temporary input text element
        inputID = 'edit_url';
        postURL = '/url/edit/';
    }

    let route;

    if (inputEl.length == 0) { // Temporary input text element does not exist, create one and inject
        route = postURL + selectedUTubID + "/" + selectedURLid;

        $('<input></input>').attr({     // Replace with temporary input
            'type': 'text',
            'id': inputID,
            'size': '30',
            'value': initString
        }).appendTo($(inputParent));

        inputEl = $('#' + inputID);
    }

    let end = inputEl[0].value.length;
    inputEl.focus();
    inputEl[0].setSelectionRange(0, end);

    inputEl.on('keyup', function (e) {        // Pressing enter is the same as blur, and submission
        if (e.keyCode === 13) {
            e.target.blur();
        }
    })

    // User submitted a card edit
    inputEl.on('blur', function (e) {

        if (inputEl[0].value != "") {
            let request = $.ajax({
                type: 'post',
                url: postURL + selectedUTubID + "/" + selectedURLid,
                data: { tag_string: inputEl[0].value }
            });

            request.done(function (response, textStatus, xhr) {
                if (xhr.status == 200) {
                    if (infoType == 'url') {
                        if (inputEl[0].value == "") {
                            inputParent[0].innerHTML = originalURL;
                        } else {
                            inputParent[0].innerHTML = inputEl[0].value;
                        }
                    } else {
                        if (inputEl[0].value != "") {
                            $('<span></span>').attr({     // Replace with temporary input
                                'class': 'tag',
                                'tagid': response.Tag.tag_ID,
                            }).appendTo($(inputParent));
                            $('.tag')[$('.tag').length - 1].innerText = inputEl[0].value  // here's where things go to shit
                        }
                    }
                    console.log("finished edit")
                    // getUtubInfo(selectedUTubID);
                    // console.log("starting to select")
                    // selectURL(selectedURLid);
                    // console.log("done selecting")
                }
            })
        }

        inputEl.remove();
    })
}