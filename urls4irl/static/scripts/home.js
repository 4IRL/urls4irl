// General UI Interactions

$(document).ready(function () {

    // Dev tracking of click-triggered objects
    $(document).click(function (e) {
        console.log($(e.target)[0])
    });

    // CSRF token initialization for non-modal POST requests
    var csrftoken = $('meta[name=csrf-token]').attr('content');
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
    $('input.active').on('blur', function () {
        console.log("Blur caught")
        var inputEl = $(this);
        console.log(inputEl)
        var handle = inputEl.attr('id');
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
            var keycode = (e.keyCode ? e.keyCode : e.which);
            var prev = keycode == 37 || keycode == 38;
            var next = keycode == 39 || keycode == 40;
            var UPRcards = $('#UPRRow').children('.cardCol').length;
            var LWRcards = $('#LWRRow').children('.cardCol').length;

            if (prev && UPRcards > 0) {              // User wants to highlight previous URL
                var cardCol = $($('#UPRRow').children('.cardCol')[UPRcards - 1]);
                selectURL($(cardCol[0].children).attr('urlid'))
            } else if (next && LWRcards > 0) {       // User wants to highlight next URL
                var cardCol = $($('#LWRRow').children('.cardCol')[0]);
                selectURL($(cardCol[0].children).attr('urlid'))
            } else {
                deselectURL($('url.selected').parent())
            }
            
        } else {
            var prev = keycode == 38;
            var next = keycode == 40;
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

    var inputDiv = $('#' + handle);
    var inputEl = inputDiv.find('input')

    // Show temporary input text element
    inputDiv.show();
    inputDiv.addClass('active');

    inputEl.focus();
    inputEl[0].setSelectionRange(0, inputEl[0].value.length);
}

// Once valid data is received from the user, this function processes it and attempts a POST request
function postData(e, handle) {
    $(e.target).parent().hide();
    var userInput = e.target.value;

    if (e.target.value) {
        switch (handle) {
            case 'createUTub':
                var postURL = '/utub/new';
                var data = { name: userInput }
                break;
            case 'createURL':
                console.log('Unimplemented')
                break;
            case 'createTag':
                var postURL = '/tag/new';
                var data = { name: userInput }
                break;
            case 'editUTubDescription':
                console.log('Unimplemented')
                break;
            case 'addTag':
                var postURL = '/tag/new/[urlid?]';
                var data = { name: userInput }
                break;
            case 'editURL':
                var postURL = '/url/edit';
                console.log('Unimplemented')
                break;
            case 'editURLDescription':
                console.log('Unimplemented')
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
                e.target.value = ''; // Clear form and get ready for new input

                switch (handle) {
                    case 'createUTub':
                        // Deselect current UTub
                        $('.UTub').removeClass('active');
                        $('input[type=radio]').prop('checked', false);

                        createUTub(response.UTub_ID, response.UTub_name)

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
    //     var jQuerySel = "div.url.selected[urlid=" + selectedURLid + "]";    // Find jQuery selector with selected ID   
    //     if (infoType == 'tag') {
    //         var inputParent = $(jQuerySel).find('div.URLTags');     // Find appropriate card element
    //         var initString = '';
    //         var inputEl = $('#new_tag');                            // Temporary input text element
    //         var inputID = 'new_tag';
    //         var postURL = '/tag/add/';
    //     } else {
    //         var inputParent = $(jQuerySel).find('p.card-text');     // Find appropriate card element         
    //         var initString = inputParent[0].innerText;              // Store pre-edit values
    //         var originalURL = inputParent[0].innerText;             // Store pre-edit values
    //         $(inputParent).html('');                                // Clear url card-text
    //         var inputEl = $('#edit_url');                           // Temporary input text element
    //         var inputID = 'edit_url';
    //         var postURL = '/url/edit/';
    //     }

    //     if (inputEl.length == 0) { // Temporary input text element does not exist, create one and inject
    //         var route = postURL + selectedUTubID + "/" + selectedURLid;

    //         $('<input></input>').attr({     // Replace with temporary input
    //             'type': 'text',
    //             'id': inputID,
    //             'size': '30',
    //             'value': initString
    //         }).appendTo($(inputParent));

    //         inputEl = $('#' + inputID);
    //     }

    //     let end = inputEl[0].value.length;
    //     inputEl.focus();
    //     inputEl[0].setSelectionRange(0, end);

    //     inputEl.on('keyup', function (e) {        // Pressing enter is the same as blur, and submission
    //         if (e.keyCode === 13) {
    //             e.target.blur();
    //         }
    //     })

    //     // User submitted a card edit
    //     inputEl.on('blur', function (e) {

    //         if (inputEl[0].value != "") {
    //             let request = $.ajax({
    //                 type: 'post',
    //                 url: postURL + selectedUTubID + "/" + selectedURLid,
    //                 data: { tag_string: inputEl[0].value }
    //             });

    //             request.done(function (response, textStatus, xhr) {
    //                 if (xhr.status == 200) {
    //                     if (infoType == 'url') {
    //                         if (inputEl[0].value == "") {
    //                             inputParent[0].innerHTML = originalURL;
    //                         } else {
    //                             inputParent[0].innerHTML = inputEl[0].value;
    //                         }
    //                     } else {
    //                         if (inputEl[0].value != "") {
    //                             $('<span></span>').attr({     // Replace with temporary input
    //                                 'class': 'tag',
    //                                 'tagid': response.Tag.tag_ID,
    //                             }).appendTo($(inputParent));
    //                             $('.tag')[$('.tag').length - 1].innerText = inputEl[0].value  // here's where things go to shit
    //                         }
    //                     }
    //                     console.log("finished edit")
    //                     // getUtubInfo(selectedUTubID);
    //                     // console.log("starting to select")
    //                     // selectURL(selectedURLid);
    //                     // console.log("done selecting")
    //                 }
    //             })
    //         }

    //         inputEl.remove();
    //     })
}