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

        $('.active').removeClass('active');
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

            resetURLDeck();
            resetTagDeck();

            // Center panel
            buildURLDeck(dictURLs, dictTags);

            // LH panels
            buildTagDeck(dictTags);

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


// Functions

function findUTubID() {
    // Find which UTub was requested
    var currentUTub = $('.UTub.active');

    var URLID = $('.url.selected').attr('urlid');

    var radioButton = currentUTub.find('input')[0];
    return radioButton.attr('utubid');
}

// Simple function to streamline the jQuery selector extraction of UTub ID. And makes it easier in case the ID is encoded in a new location in the future
function currentUTubID() {
    return $('.UTub.active').find('input').attr('utubid');
}

// Simple function to streamline the jQuery selector extraction of URL ID. And makes it easier in case the ID is encoded in a new location in the future
function selectedURLID() {
    console.log($('.url.selected').attr('urlid'))
    return $('.url.selected').attr('urlid');
}

// Simple function to streamline the AJAX call to db for updated info
function getUtubInfo(selectedUTubID) {
    // Pull data from db
    return $.getJSON('/home?UTubID=' + selectedUTubID)
    // $.getJSON('/home?UTubID=' + selectedUTubID, function (selectedUTub) {
    //     console.log(selectedUTub)

    //     return selectedUTub

    // Maybe rebuild elsewhere as required
    //Use local variables, pass them in to the subsequent functions as required
    // var selectedUTubID = selectedUTub.id;
    // var dictURLs = selectedUTub.urls;
    // var dictTags = selectedUTub.tags;
    // var dictUsers = selectedUTub.members;
    // var creator = selectedUTub.created_by;
    // let currentUserID = $('.user').attr('id');

    // // Clear URL Deck and prep for new UTub data
    // resetURLDeck();

    // // Center panel
    // buildURLDeck(dictURLs, dictTags);

    // // LH panels
    // buildTagDeck(dictTags);

    // // RH panels
    // // Update UTub description, not yet implemented on backend
    // // $('#UTubInfo')[0].innerHTML = selectedUTub.description;

    // gatherUsers(dictUsers, creator);
    // })
}

function buildUTubDeck(UTubs) {
    if (UTubs.length == 0) {
        // User has no UTubs
        $('#UTubHeader')[0].innerHTML = "<------------------------- Oops, no UTubs! Create one!";
        $('#UTubDeck').find('h2')[0].innerHTML = "Create a UTub";
    } else {
        // Instantiate UTubDeck (top left panel) with UTubs accessible to current user
        $('#UTubDeck').find('h2')[0].innerHTML = "UTubs";

        const parent = $('#listUTubs')

        for (i in UTubs) {
            let label = document.createElement('label');
            let radio = document.createElement('input');

            $(label).attr({
                'for': 'UTub-' + UTubs[i].id,
                'class': 'UTub draw'
            })
            label.innerHTML = '<b>' + UTubs[i].name + '</b>';

            $(radio).attr({
                'type': 'radio',
                'name': 'UTub' + i,
                'id': 'UTub-' + UTubs[i].id,
                'utubid': UTubs[i].id,
                'value': UTubs[i].name
            })

            $(label).append(radio);
            parent.append(label);
        }

        // New UTub input text field. Initially hidden, shown when create UTub is requested. Input field recreated here to ensure at the end of list after creation of new UTubs
        let input = document.createElement('input');
        $(input).attr({
            'type': 'text',
            'id': 'createUTub',
            'utubid': 0,
            'class': 'userInput',
            'placeholder': 'New UTub name',
            'size': '30',
            'style': 'display: none'
        })

        parent.append(input);

        // Old HTML way. Changed 01/02/23 for consistency with buildURLDeck and improved code clarity
        // radioHTML = '';
        // for (i in UTubs) {
        //     radioHTML += '<label for="UTub-' + UTubs[i].id + '" class="UTub draw"><input type="radio" name="UTub-' + UTubs[i].id + '" id="UTub-' + UTubs[i].id + '" utubid=' + UTubs[i].id + ' name="UTubSelection" value="' + UTubs[i].name + '"><b>' + UTubs[i].name + '</b></label>';
        // }
        // $('#listUTubs')[0].innerHTML = radioHTML + $('#listUTubs')[0].innerHTML;
    }
}

// Build LH panel tag list in selectedUTub
function buildTagDeck(dictTags) {
    if (dictTags.length == 0) {
        // User has no Tags in this UTub
        $('#TagDeck').find('h2')[0].innerHTML = "Create a Tag";
        $('#listTags')[0].innerHTML = '<h5>No Tags Applied to any URLs in this UTub</h5>'; // I still want this to show if user creates a new tag but has not yet applied them to any URLs
    } else {
        // Instantiate UTubDeck (top left panel) with UTubs accessible to current user
        $('#TagDeck').find('h2')[0].innerHTML = "Tags";

        const parent = $('#listTags')

        // Start with the select all checkbox
        let container = document.createElement('div');
        let label = document.createElement('label');
        let selAllCheck = document.createElement('input');

        
        $(container).attr({ 'class': 'checkbox-container' })

        $(label).attr({ 'for': 'selectAll' })

        $(selAllCheck).attr({
            'type': 'checkbox',
            'id': 'selectAll',
            'name': 'selectAll',
            'checked': 'true'
        })

        $(label).append(selAllCheck);
        label.innerHTML += 'Select All';
        $(container).append(label);
        parent.append(container);

        // Alpha sort tags based on tag_string
        dictTags.sort(function (a, b) {
            const tagA = a.tag_string.toUpperCase(); // ignore upper and lowercase
            const tagB = b.tag_string.toUpperCase(); // ignore upper and lowercase
            if (tagA < tagB) {
                return -1;
            }
            if (tagA > tagB) {
                return 1;
            }
            // tags must be equal
            return 0;
        });

        // Loop through all tags and provide checkbox input for filtering
        for (let i in dictTags) {
            let tagText = dictTags[i].tag_string;
            let tagID = dictTags[i].id;
            let container = document.createElement('div');
            let label = document.createElement('label');
            let checkbox = document.createElement('input');

            $(container).attr({ 'class': 'checkbox-container' })

            $(label).attr({ 'for': 'Tag-' + tagID })

            $(checkbox).attr({
                'type': 'checkbox',
                'id': 'Tag-' + tagID,
                'tagid': tagID,
                'name': 'Tag' + i,
                'checked': 'true'
            })

            $(label).append(checkbox);
            label.innerHTML += tagText;
            $(container).append(label);
            parent.append(container);
        }
         // New UTub input text field. Initially hidden, shown when create UTub is requested. Input field recreated here to ensure at the end of list after creation of new UTubs
         let input = document.createElement('input');
         $(input).attr({
             'type': 'text',
             'id': 'createTag',
             'tagid': 0,
             'class': 'userInput',
             'placeholder': 'New Tag name',
             'size': '30',
             'style': 'display: none'
         })
 
         parent.append(input);
    }
}

// Build center panel URL-tag list for selectedUTub
function buildURLDeck(dictURLs, dictTags) {

    $('#editUTub').show();
    $('#addURL').show();
    $('#UTubDescription').show();

    let selectedUTubID = currentUTubID();

    for (let i in dictURLs) {
        let col = document.createElement('div');
        let card = document.createElement('div');
        // let cardImg = document.createElement('img');
        let urlInfo = document.createElement('div');
        let urlDescription = document.createElement('h5');
        let urlString = document.createElement('p');
        let urlTags = document.createElement('div');
        let urlOptions = document.createElement('div');
        let accessURL = document.createElement('button');
        let addTag = document.createElement('button');
        let editURL = document.createElement('button');
        let delURL = document.createElement('button');

        $(col).attr({ 'class': 'cardCol mb-3 col-md-10 col-lg-4 col-xl-3' })

        $(card).attr({
            'urlid': dictURLs[i].url_id,
            'class': 'card url',
            'draggable': 'true',
            'ondrop': 'dropIt(event)',
            'ondragover': 'allowDrop(event)',
            'ondragstart': 'dragStart(event)'
        })

        // $(cardImg).attr({
        //     'class': 'card-img-top',
        //     'src': '...',
        //     'alt': '"Card image cap'
        // })

        $(urlInfo).attr({ 'class': 'card-body URLInfo' })

        $(urlDescription).attr({ 'class': 'card-title' })
        urlDescription.innerHTML = dictURLs[i].url_description ? dictURLs[i].url_description : ''

        $(urlString).attr({ 'class': 'card-text' })
        urlString.innerHTML = dictURLs[i].url_string;

        $(urlTags).attr({ 'class': 'card-body URLTags', 'style': 'display: none' })

        // Build tag html strings 
        let tagArray = dictURLs[i].url_tags;
        for (let j in tagArray) { // Find applicable tags in dictionary to apply to URL card
            let tag = dictTags.find(function (e) {
                if (e.id === tagArray[j]) {
                    return e
                }
            });

            let tagSpan = document.createElement('span');
            let closeButton = document.createElement('a');

            $(tagSpan).attr({
                'class': 'tag',
                'tagid': tag.id,
            });
            tagSpan.innerHTML = tag.tag_string;

            $(closeButton).attr({
                'class': 'btn btn-sm btn-outline-link border-0 tag-del',
                'onclick': 'removeTag(' + tag.id + ')'
            });
            closeButton.innerHTML = '&times;';

            $(tagSpan).append(closeButton);
            $(urlTags).append(tagSpan);
        }

        $(urlOptions).attr({ 'class': 'card-body URLOptions', 'style': 'display: none' })

        $(accessURL).attr({
            'class': 'card-link btn btn-primary',
            'type': 'button',
            'onclick': "accessLink('" + dictURLs[i].url_string + "')"
        })
        accessURL.innerHTML = "Access Link"

        $(addTag).attr({
            'class': 'card-link btn btn-info',
            'type': 'button',
            // 'onclick': "reqInput('addTag')"
            'onclick': "cardEdit(" + selectedUTubID + "," + dictURLs[i].url_id + ",'tag')"
        })
        addTag.innerHTML = "Add Tag"

        $(editURL).attr({
            'class': 'card-link btn btn-warning',
            'type': 'button',
            'onclick': "cardEdit(" + selectedUTubID + "," + dictURLs[i].url_id + ",'url')"
        })
        editURL.innerHTML = "Edit URL"

        $(delURL).attr({
            'class': 'card-link btn btn-danger',
            'type': 'button',
            'onclick': "deleteURL()"
            // "/delete_url/" + selectedUTubID + "/" + dictURLs[i].url_id
        })
        delURL.innerHTML = "Delete URL"

        // Assemble url list items
        $(col).append(card);
        // $(card).append(cardImg);
        $(card).append(urlInfo);
        $(urlInfo).append(urlDescription);
        $(urlInfo).append(urlString);
        $(card).append(urlTags);
        $(card).append(urlOptions);
        $(urlOptions).append(accessURL);
        $(urlOptions).append(addTag);
        $(urlOptions).append(editURL);
        $(urlOptions).append(delURL);

        UPRRow.append(col);
    }
}

// Request user text input by placing a text input element in the appropriate location and await valid input
function reqInput(handle) {

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

    // // User submitted a card edit
    // // If it's empty (or otherwise invalid), do not POST and simply remove the input element
    // inputEl.on('blur', function (e) {

    //     if (document.activeElement.localname == 'input') {
    //         return;
    //     }

    //     if (inputEl[0].value) {
    //         postData(inputEl[0].value, handle)
    //     } else {
    //         // Input is empty
    //     }
    //     inputEl.hide();
    //     inputEl.removeClass('active');
    // })
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

// Handle all display changes related to creating a new UTub
function createUTub(id, name) {
    radioHTML = '<label for="UTub-' + id + '" class="UTub draw active"><input type="radio" id="UTub-' + id + '" utubid=' + id + ' name="UTubSelection" value="' + name + '"><b>' + name + '</b></label>';
    $('#listUTubs')[0].innerHTML += radioHTML;

    $('#UTub-' + id).prop('checked', true);
    $('#UTub-' + id).closest('.UTub').addClass('active');

    $('#UTubHeader')[0].innerHTML = name;
    $('#UPRRow')[0].innerHTML = "Add a URL";
}

// Edit UTub name and description. Should automatically run after creation of a new UTub to offer the option of including a UTub description.
function editUTub() {
    reqInput('editUTub')
    reqInput('editUTubDescription')

    radioHTML = '<label for="UTub-' + id + '" class="UTub draw active"><input type="radio" id="UTub-' + id + '" utubid=' + id + ' name="UTubSelection" value="' + name + '"><b>' + name + '</b></label>';
    $('#listUTubs')[0].innerHTML += radioHTML;

    $('#UTub-' + id).prop('checked', true);
    $('#UTub-' + id).closest('.UTub').addClass('active');

    $('#UTubHeader')[0].innerHTML = name;
    $('#UPRRow')[0].innerHTML = "Add a URL";
}

// Add a tag to the selected URL
function addTag(selectedUTubID, selectedURLid) {
    var jQuerySel = "div.url.selected[urlid=" + selectedURLid + "]";    // Find jQuery selector with selected ID          
    var cardTagDeck = $(jQuerySel).find('div.URLTags');                 // Find appropriate card element

    if ($('#new_tag').length) $('#new_tag').focus()
    else {
        $('<input></input>').attr({     // Replace with temporary input
            'type': 'text',
            'id': 'new_tag',
            'size': '30'
        }).appendTo($(cardTagDeck));
        $('#new_tag').focus()
    }

    $('#new_tag').on('blur keyup', function (e) {
        var keycode = (e.keyCode ? e.keyCode : e.which);
        if (e.type === 'blur' || keycode == '13') {
            var tagText = $(this).val();                    // Need to send this back to the db somehow
            let request = $.ajax({
                type: 'post',
                url: "/tag/add/" + selectedUTubID + "/" + selectedURLid,
                data: tagText
            });

            request.done(function (response, textStatus, xhr) {
                if (xhr.status == 200) {
                    cardTagDeck[0].innerHTML = updatedURLText;
                } else {
                    URLStringField[0].innerHTML = updatedURLText;
                }
            })
        }
    })
}

// Add a URL to current UTub
function addURL(selectedUTubID) {
    var jQuerySel = "div.url.selected[urlid=" + selectedURLid + "]";    // Find jQuery selector with selected ID          
    var cardTagDeck = $(jQuerySel).find('div.URLTags');                 // Find appropriate card element

    if ($('#new_tag').length) $('#new_tag').focus()
    else {
        $('<input></input>').attr({     // Replace with temporary input
            'type': 'text',
            'id': 'new_tag',
            'size': '30'
        }).appendTo($(cardTagDeck));
        $('#new_tag').focus()
    }

    $('#new_tag').on('blur keyup', function (e) {
        var keycode = (e.keyCode ? e.keyCode : e.which);
        if (e.type === 'blur' || keycode == '13') {
            var tagText = $(this).val();                    // Need to send this back to the db somehow
            let request = $.ajax({
                type: 'post',
                url: "/tag/add/" + selectedUTubID + "/" + selectedURLid,
                data: tagText
            });

            request.done(function (response, textStatus, xhr) {
                if (xhr.status == 200) {
                    cardTagDeck[0].innerHTML = updatedURLText;
                } else {
                    console.log("Didn't work yet but I'll let it slide for now (needs POST route)")
                    URLStringField[0].innerHTML = updatedURLText;
                }
            })
        }
    })
}
// Update URL deck to reflect changes in response to a user change of tag options
function filterURLDeck() {
    let URLcardst = $('div.url');
    for (let i = 0; i < URLcardst.length; i++) {
        let tagList = $(URLcardst[i]).find('span.tag');

        // If no tags associated with this URL, ignore. Unaffected by filter functionality
        if (tagList.length === 0) { continue; }

        // If all tags for given URL are style="display: none;", hide parent URL card
        let inactiveTagBool = tagList.map(i => tagList[i].style.display == 'none' ? true : false)
        // Manipulate mapped Object
        let boolArray = Object.entries(inactiveTagBool);
        boolArray.pop();
        boolArray.pop();

        // Default to hide URL
        let hideURLBool = true;
        boolArray.forEach(e => hideURLBool &= e[1])

        // If url <div.card.url> has no tag <span>s in activeTagIDs, hide card column (so other cards shift into its position)
        if (hideURLBool) { $(URLcardst[i]).parent().hide(); }
        // If tag reactivated, show URL
        else { $(URLcardst[i]).parent().show(); }
    }
}

// Remove tag from selected URL
function removeTag(tagID) {
    var UTubID = currentUTubID();
    var URLID = selectedURLID();

    let request = $.ajax({
        type: 'post',
        url: '/tag/remove/' + UTubID + '/' + URLID + '/' + tagID
    });

    request.done(function (response, textStatus, xhr) {
        if (xhr.status == 200) {
            console.log($('div.url[urlid=' + URLID + ']'))
            console.log($('div.url[urlid=' + URLID + ']').find('span.tag[' + tagID + ']'))
            $('div.url[urlid=' + URLID + ']').find('span.tag[tagid=' + tagID + ']').remove();
        }
    })

    request.fail(function (xhr, textStatus, error) {
        if (xhr.status == 409) {
            console.log("Failure. Status code: " + xhr.status + ". Status: " + textStatus);
        } else if (xhr.status == 404) {
            $('.invalid-feedback').remove();
            $('.alert').remove();
            $('.form-control').removeClass('is-invalid');
            const error = JSON.parse(xhr.responseJSON);
            for (var key in error) {
                $('<div class="invalid-feedback"><span>' + error[key] + '</span></div>')
                    .insertAfter('#' + key).show();
                $('#' + key).addClass('is-invalid');
            };
        };
        console.log("Failure. Status code: " + xhr.status + ". Status: " + textStatus);
        console.log("Error: " + error);
    })
}

// A URL is already selected, user would like to unselect (or potentially select another)
function deselectURL(deselectedCardCol) {
    var card = deselectedCardCol.find('.card');
    deselectedCardCol.addClass('col-lg-4 col-xl-3');
    deselectedCardCol.removeClass('col-lg-10 col-xl-10');
    card.removeClass('selected');
    card.find('.URLTags').css('display', 'none');
    card.find('.URLOptions').css('display', 'none');
}

// User selects a URL. All other URLs are deselected. This function places all URLs prior to selected URL into #UPRRow, inserts selected URL into a separate #URLFocusRow, and places all subsequent URLs into #LWRRow. It also adjusts css displays accordingly
function selectURL(selectedURLid) {
    var cardCols = $('.cardCol');

    let rowToggle = 1; // ? Add to UPR row : Add to LWR row
    var activeRow = $('#UPRRow');

    // Loop through all cardCols and add to UPR row until selected URL card, then subsequent cardCols are added to LWR row
    for (let i = 0; i < cardCols.length; i++) {
        let card = $(cardCols[i]).find('.card');
        let URLid = card.attr('urlid');

        if (URLid == selectedURLid) {
            $('#URLFocusRow').append(cardCols[i]);
            $(cardCols[i]).toggleClass('col-lg-10 col-lg-4 col-xl-10 col-xl-3')
            card.addClass('selected')
            card.attr('draggable', '')
            card.find('.URLTags').css('display', '');
            card.find('.URLOptions').css('display', '');
            rowToggle = 0;
        } else {
            deselectURL($(cardCols[i]))
            activeRow.append(cardCols[i]);
        }

        activeRow = rowToggle ? $('#UPRRow') : $('#LWRRow');
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

// Clear the Tag Deck
function resetTagDeck() {
    $('#listTags').empty();
}

// Clear the URL Deck
function resetURLDeck() {
    console.log($('#URLFocusRow')[0].children)
    
    // Empty URL Deck
    $('#UPRRow').empty();
    $('#URLFocusRow').empty();
    $('#LWRRow').empty();
}


function accessLink(url_string) {
    // Still need to implement: Take user to a new tab with interstitial page warning they are now leaving U4I
    if (!url_string.startsWith('https://')) {
        window.open('https://' + selectedURL.url_string, "_blank");
    } else {
        window.open(url_string, "_blank");
    }
}

// function addTag(selectedUTubID, selectedURLid) {
//     let urlTagDeck = $('.selected').find('.URLTags');
//     // Create temporary, editable element
//     let tagInput = document.createElement('input');
//     let newTag = document.createElement('span');
//     $(tagInput).attr({
//         'type': 'text',
//         'id': 'newTag',
//         'class': 'tag'
//     })
//     urlTagDeck.append(tagInput);
//     $('#newTag').focus();

//     $('#newTag').on('blur keyup', function (e) {
//         var tagText = $(this).val();
//         if (tagText == '') return;
//         if (e.type === 'blur') {
//             let request = $.ajax({
//                 url: "/add_tag/" + selectedUTubID + "/" + selectedURLid,
//                 type: 'POST',
//                 data: tagText
//             });

//             // $(newTag).attr({
//             //     'tagid': '1',
//             //     'class': 'tag'
//             // })

//             // newTag.innerHTML = tagText;
//             // console.log(newTag.innerHTML)
//             // $('#newTag').remove();
//             // urlTagDeck.append(newTag);

//             request.done(function (response, textStatus, xhr) {
//                 if (xhr.status == 200) {
//                     console.log(response)

//                     // Create final display element
//                     let tagSpan = document.createElement('span');
//                     $(tagSpan).attr({
//                         'tagid': '1',
//                         'class': 'tag',
//                         'tagid': response.id,
//                         'value': response.tag_string
//                     })
//                     $('.selected.URLTags').append(tagSpan)
//                 }
//             })
//         }
//     })

// }

function cardEdit(selectedUTubID, selectedURLid, infoType) {
    var jQuerySel = "div.url.selected[urlid=" + selectedURLid + "]";    // Find jQuery selector with selected ID   
    if (infoType == 'tag') {
        var inputParent = $(jQuerySel).find('div.URLTags');     // Find appropriate card element
        var initString = '';
        var inputEl = $('#new_tag');                            // Temporary input text element
        var inputID = 'new_tag';
        var postURL = '/tag/add/';
    } else {
        var inputParent = $(jQuerySel).find('p.card-text');     // Find appropriate card element         
        var initString = inputParent[0].innerText;              // Store pre-edit values
        var originalURL = inputParent[0].innerText;             // Store pre-edit values
        $(inputParent).html('');                                // Clear url card-text
        var inputEl = $('#edit_url');                           // Temporary input text element
        var inputID = 'edit_url';
        var postURL = '/url/edit/';
    }

    if (inputEl.length == 0) { // Temporary input text element does not exist, create one and inject
        var route = postURL + selectedUTubID + "/" + selectedURLid;

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

function confirmModal(handle) {

    // Modal adjustments
    switch (handle) {
        case 'deleteUTub':
            var modalTitle = 'Are you sure you want to delete this UTub?'
            break;
        case 'deleteUser':
            var modalTitle = 'Are you sure you want to remove this user from the current UTub?'
            break;
        default:
            console.log('Unimplemented')
    }

    $('.modal-title')[0].innerHTML = modalTitle

    $('#confirmModal').modal('show');

    $('#submit').click(function (e) {
        e.preventDefault();
        switch (handle) {
            case 'deleteUTub':
                deleteUTub()
                break;
            case 'deleteUser':
                removeUser()
                break;
            default:
                console.log('Unimplemented')
        }
    })
}

function deleteUTub() {
    var id = currentUTubID();

    let request = $.ajax({
        type: 'post',
        url: "/utub/delete/" + id
    });

    request.done(function (response, textStatus, xhr) {
        if (xhr.status == 200) {
            // Clear URL Deck
            resetURLDeck();
            resetTagDeck();

            // Update UTub Deck
            $('#UTub-' + id).parent().remove();

            // Update UTub center panel
            $('#UTubHeader')[0].innerHTML = "Select a UTub";
            $('#editUTub').hide();
            $('#addURL').hide();
            $('#UTubDescription').hide();
        }
    })

    request.fail(function (xhr, textStatus, error) {
        if (xhr.status == 409) {
            console.log("Failure. Status code: " + xhr.status + ". Status: " + textStatus);
            // const flashMessage = xhr.responseJSON.error;
            // const flashCategory = xhr.responseJSON.category;

            // let flashElem = flashMessageBanner(flashMessage, flashCategory);
            // flashElem.insertBefore('#modal-body').show();
        } else if (xhr.status == 404) {
            $('.invalid-feedback').remove();
            $('.alert').remove();
            $('.form-control').removeClass('is-invalid');
            const error = JSON.parse(xhr.responseJSON);
            for (var key in error) {
                $('<div class="invalid-feedback"><span>' + error[key] + '</span></div>')
                    .insertAfter('#' + key).show();
                $('#' + key).addClass('is-invalid');
            };
        };
        console.log("Failure. Status code: " + xhr.status + ". Status: " + textStatus);
        console.log("Error: " + error);
    })
}

function deleteURL() {
    var URLID = selectedURLID()

    let request = $.ajax({
        type: 'post',
        url: "/url/remove/" + currentUTubID() + "/" + URLID
    });

    request.done(function (response, textStatus, xhr) {
        if (xhr.status == 200) {
            let cardCol = $('div[urlid=' + URLID + ']').parent()
            cardCol.fadeOut();
            cardCol.remove();
        }
    })

    request.fail(function (xhr, textStatus, error) {
        if (xhr.status == 409) {
            console.log("Failure. Status code: " + xhr.status + ". Status: " + textStatus);
            // const flashMessage = xhr.responseJSON.error;
            // const flashCategory = xhr.responseJSON.category;

            // let flashElem = flashMessageBanner(flashMessage, flashCategory);
            // flashElem.insertBefore('#modal-body').show();
        } else if (xhr.status == 404) {
            $('.invalid-feedback').remove();
            $('.alert').remove();
            $('.form-control').removeClass('is-invalid');
            const error = JSON.parse(xhr.responseJSON);
            for (var key in error) {
                $('<div class="invalid-feedback"><span>' + error[key] + '</span></div>')
                    .insertAfter('#' + key).show();
                $('#' + key).addClass('is-invalid');
            };
        };
        console.log("Failure. Status code: " + xhr.status + ". Status: " + textStatus);
        console.log("Error: " + error.Error_code);
    })
}