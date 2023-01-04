// UI Interactions
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

    // Instantiate UTubDeck with user's accessible UTubs
    buildUTubDeck(UTubsList);

    // User selected a UTub, display data
    $('input[type=radio]').on('click', function () {
        console.log("New Utub selected")

        $('#listUTubs').find('.active').removeClass('active');
        $(this).parent().toggleClass('active');
        $('#UTubHeader')[0].innerHTML = $(this)[0].value;

        var selectedUTubID = currentUTubID();
        getUtubInfo(selectedUTubID).then(function (selectedUTub) {
            //Use local variables, pass them in to the subsequent functions as required
            var dictURLs = selectedUTub.urls;
            var dictTags = selectedUTub.tags;
            var dictUsers = selectedUTub.members;
            var creator = selectedUTub.created_by;
            let currentUserID = $('.user').attr('id');

            resetTagDeck();
            resetURLDeck();

            // LH panel
            buildTagDeck(dictTags);

            // Center panel
            buildURLDeck(dictURLs, dictTags);

            // RH panels
            // Update UTub description, not yet implemented on backend
            // $('#UTubInfo')[0].innerHTML = selectedUTub.description;

            gatherUsers(dictUsers, creator);
        })
    });

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

    }).on('keyup', function (e) {
        if (e.keyCode === 13) {
            e.preventDefault();
            e.target.blur();
        }
    })

    // Selected URL. Hide/show the card, if nothing "important" in card was clicked)
    $(document).on('click', '.card', function (e) {
        // e.stopPropagation();
        // e.stopImmediatePropagation();
        // Triage click
        var el = $(e.target);

        var importantBool = el.hasClass('btn') || el.hasClass('tag') || el[0].type == 'text';
        if (importantBool) {
            // "Important" thing clicked. Do nothing. onclick function will handle user inputs
        } else {
            var clickedCardCol = $(e.target).closest('.cardCol');   // Card column
            var clickedCard = clickedCardCol.find('.card');         // Card
            var selectedURLid = clickedCard.attr('urlid');          // URL ID

            if (clickedCard.hasClass("selected")) {
                $('.cardCol').each(function () {
                    $('#UPRRow').append(this)
                })
                deselectURL(clickedCardCol);
            } else selectURL(selectedURLid);
        }
    });

    // Selected Tag
    $('#TagDeck').on('click', function (e) {
        // Refactor into separate function at some point
        let label;
        let input;
        let clickedTagID;
        if (e.target.nodeName.toLowerCase() == 'label') {
            // Label clicked. Reset input var. Also toggles checkbox and assigns clickedTagID
            label = $(e.target);
            input = label.children();
            input.prop("checked", !input.prop("checked"));
        } else {
            // Input clicked. Already toggles checkbox
            input = $(e.target);
            label = input.parent();
        }

        if (input[0].id == 'selectAll') {

            if (e.target.nodeName.toLowerCase() == 'label') {
                e.preventDefault();
            }

            // Toggle all filter tags
            $('input[type=checkbox]').prop("checked", input[0].checked);

            // Hide/Show all tag spans
            spanObjs = $('span.tag')
            if (input[0].checked) {
                $($(spanObjs)).show()
            } else {
                $($(spanObjs)).hide()
            }
        } else {

            let selectAllBool = true;
            $('input[type=checkbox]').each(function (i) {
                if (i !== 0) {
                    selectAllBool &= $(this).prop("checked");
                }
            })

            $('#selectAll').prop("checked", selectAllBool);

            clickedTagID = parseInt(label.attr("tagid"));

            // Hide/Show corresponding tag span
            spanObjs = $('span[tagid="' + clickedTagID + '"]')
            $($(spanObjs)).toggle()
        }

        // Update URLs displayed as a result of checkbox filtering
        filterURLDeck();
    });

    // Listen for click on toggle checkbox
    $('#selectAll').click(function (event) {
        if (this.checked) {
            // Iterate each checkbox
            $(':checkbox').each(function () {
                this.checked = true;
            });
        } else {
            $(':checkbox').each(function () {
                this.checked = false;
            });
        }
    });

    // Remove tag from URL
    $('.tag-del').click(function (e) {
        console.log("Tag deletion initiated")
        e.stopImmediatePropagation();
        const tagToRemove = $(this).parent();
        const tagID = tagToRemove.attr('tagid');
        removeTag(tagToRemove, tagID);
    });


    $(document).on('keyup', function (e) {
        if ($('#URLFocusRow').length > 0) {     // Some URL is selected
            var keycode = (e.keyCode ? e.keyCode : e.which);
            var prev = keycode == 37 || keycode == 38;
            var next = keycode == 39 || keycode == 40;
            var UPRcards = $('#UPRRow').children('.cardCol').length;
            var LWRcards = $('#LWRRow').children('.cardCol').length;

            console.log(prev)
            console.log(UPRcards)
            console.log(next)
            console.log(LWRcards)

            if (prev && UPRcards > 0) {              // User wants to highlight previous URL
                var cardCol = $($('#UPRRow').children('.cardCol')[UPRcards - 1]);
                console.log(cardCol[0].children[0])
                selectURL(cardCol.children.attr('urlid'))
            } else if (next && LWRcards > 0) {       // User wants to highlight next URL
                console.log($($('#LWRRow').children('.cardCol')))
                selectURL($($('#LWRRow').children('.cardCol')[0]).attr('urlid'))
            }
        }
    })

    // Selected User (only if creator)
    $('select').change(function () {
        // Update href
        $('#removeUserTemp').attr("action", '/remove_user/' + selectedUTubID + '/' + $(this)[0].value)
    })

    // Update UTub description (only if creator)
    $('#UTubInfo').on('input', function () {
        //handle update in db
    })

    // Update URL description
    $('#URLInfo').on('input', function () {
        //handle update in db
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

// Request user text input by placing a text input element in the appropriate location and await valid input
function showInput(handle) {

    var inputEl = $('#' + handle);

    // Show temporary input text element
    inputEl.show();
    inputEl.addClass('active');

    inputEl.focus();
    inputEl[0].setSelectionRange(0, inputEl[0].value.length);

    // // Pressing enter is the same as blur, implying submission. Not currently working 
    // inputEl.submit(function (e) {
    //     e.preventDefault();
    //     e.target.blur();
    // })
    // inputEl.on('keyup', function (e) {
    //     if (e.keyCode === 13) {
    //         e.preventDefault();
    //         e.target.blur();
    //     }
    // })

    // // NICE TO HAVE: Prevent other click behaviors on page only ONCE while editing. This will avoid behaviors like card minimizing/deselecting immediately after editing card
    // // $(document).click(function (e) {
    // //     console.log("Don't do anything else")
    // //     console.log(e)
    // //     e.stopImmediatePropagation();
    // //     e.target.blur();
    // // });

    // // $(document).on('click', function (e) {
    // //     console.log("Don't do anything else")
    // //     console.log(e)
    // //     e.stopImmediatePropagation();
    // //     e.target.blur();
    // // });
}

function hideInput(e) {
    $(e.target).parent().hide();
    console.log(e.target.value)
}

// Once valid data is received from the user, this function processes it and attempts a POST request
function postData(userInput, handle) {
    console.log(handle)

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
            switch (handle) {
                case 'createUTub':
                    // // Deselect current UTub
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