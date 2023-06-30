// URL UI Interactions


$(document).ready(function () {

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

    // Remove tag from URL
    $('.tag-remove').click(function (e) {
        console.log("Tag removal initiated")
        e.stopImmediatePropagation();
        const tagToRemove = $(this).parent();
        const tagID = tagToRemove.attr('tagid');
        removeTag(tagToRemove, tagID);
    });


});

// URL Functions

// Simple function to streamline the jQuery selector extraction of URL ID. And makes it easier in case the ID is encoded in a new location in the future
function selectedURLID() {
    return $('.url.selected').last().attr('urlid');
}

// Build center panel URL-tag list for selectedUTub
function buildURLDeck(dictURLs, dictTags) {

    $('#editUTubButton').show();
    $('#addURL').show();
    $('#UTubDescription').show();

    let selectedUTubID = currentUTubID();

    for (let i in dictURLs) {

        let URLcol = createURL(dictURLs[i].url_id, dictURLs[i].url_string, dictURLs[i].notes, dictURLs[i].url_tags, selectedUTubID, dictTags)

        UPRRow.append(URLcol);
    }

    // New URL create block
    let URLcol = createURL(0, '', '', '', selectedUTubID, [])

    URLFocusRow.append(URLcol);
    // I actually don't know how 'UPRRow' and 'URLFocusRow' are referenced...
}

// Add a URL to current UTub
function createURL(URLID, string, description, tagArray, UTubID, dictTags) {
    let col = document.createElement('div');
    let card = document.createElement('div');
    // let cardImg = document.createElement('img');
    let urlInfo = document.createElement('div'); // This element holds the URL description and string
    let urlDescription = document.createElement('h5'); // This element displays the user-created description of the URL
    let urlString = document.createElement('p'); // This element displays the user's URL
    let editWrap1 = document.createElement('div'); // This element wraps the edit field for URL description
    let editURLDescription = document.createElement('input'); // This element is instantiated with the URL description, or is blank for the creation block
    let editWrap2; // This element wraps the edit field for URL string 
    let editURLString = document.createElement('input'); // This element is instantiated with the URL, or is blank for the creation block
    let urlTags = document.createElement('div');
    let urlOptions = document.createElement('div');
    let accessURL = document.createElement('button');
    let addTag = document.createElement('button');
    let editURL = document.createElement('button');
    let submit = document.createElement('i');
    let delURL = document.createElement('button');

    $(col).attr({ 'class': 'cardCol mb-3 col-md-10' })

    $(card).attr({
        'urlid': URLID,
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
    urlDescription.innerHTML = description ? description : ''

    $(editWrap1).attr({
        'class': 'createDiv',
        'style': 'display: none'
    })

    $(editURLDescription).attr({
        'type': 'text',
        'class': 'card-title userInput',
        'size': '50'
    })

    $(urlString).attr({ 'class': 'card-text' })
    urlString.innerHTML = string

    $(editURLString).attr({
        'type': 'text',
        'class': 'card-text userInput',
        'size': '50'
    })

    $(urlTags).attr({ 'class': 'card-body URLTags' })

    // Build tag html strings 
    for (let j in tagArray) { // Find applicable tags in dictionary to apply to URL card
        let tag = dictTags.find(function (e) {
            if (e.id === tagArray[j]) {
                return e
            }
        });

        let tagSpan = createTaginURL(tag.id, tag.tag_string, 0)

        $(urlTags).append(tagSpan);
    }

    // New tag create span    
    let tagInput = createTaginURL(0, '', URLID)

    $(urlTags).append(tagInput);

    $(urlOptions).attr({ 'class': 'card-body URLOptions' })

    $(accessURL).attr({
        'class': 'card-link btn',
        'type': 'button'
    })

    $(addTag).attr({
        'class': 'card-link btn btn-info',
        'type': 'button',
        'onclick': "showInput('addTag-" + URLID + "')"
    })
    addTag.innerHTML = "Add Tag"

    $(editURL).attr({
        'class': 'card-link btn btn-warning editBtn',
        'type': 'button'
    })
    editURL.innerHTML = "Edit"

    $(submit).attr({
        'id': 'submitEditURL-'+ URLID ,
        'class': 'fa fa-check-square fa-2x text-success mx-1',
        'type': 'button',
        'style': 'display: none'
    })

    $(delURL).attr({
        'class': 'card-link btn btn-danger',
        'type': 'button'
    })

    // Creation URL specific items
    if (URLID == 0) {
        // New URL card and input text fields. Initially hidden, shown when create URL is requested. Input field recreated here to ensure at the end of list after creation of new URL
        $(col).attr({
            'id': 'createURL',
            'class': 'createDiv col-lg-10 col-xl-10',
            'style': 'display: none',
            'onblur': 'hideInput(event)'
        })

        $(card).addClass('selected')

        $(editURLDescription).attr({
            'id': 'newURLDescription',
            'placeholder': 'New URL description'
        })

        $(editURLString).attr({
            'id': 'newURL',
            'placeholder': 'New URL'
        })

        // Buttons
        $(accessURL).attr({ 'onclick': 'postData(event, "createURL")' })
        $(accessURL).addClass('btn-success')
        accessURL.innerHTML = "Create URL"
        // $(addTag).attr({ 'onclick': "showInput('addTag')" })
        $(editURL).attr({
            // Re-highlight input field?
            // 'onclick': "cardEdit(" + selectedUTubID + "," + dictURLs[i].url_id + ",'url')" should refocus on URL input
            // 'onclick': "(function(){ alert('Hey i am calling'); return false; })();return false;"
        })
        $(delURL).attr({
            // Cancel creation, reset fields?
            'onclick': "$('#createURL').hide()"
        })
        delURL.innerHTML = "Cancel"
    } else {
        $(col).addClass('col-lg-4 col-xl-3')

        let editURLDescriptionid = 'editURLDescription-' + URLID;
        let editURLid = 'editURL-' + URLID;

        $(editURLDescription).attr({
            'id': editURLDescriptionid,
            'value': description ? description : '',
            'placeholder': 'Edit URL Description',
            // 'onblur': "postData(event, '" + editURLid + "')"
        })

        $(editURLString).attr({
            'id': editURLid,
            'value': string,
            'placeholder': 'Edit URL',
            // 'onblur': "postData(event, '" + editURLid + "')"
        })

        $(urlOptions).append(accessURL);

        $(urlTags).attr({ 'style': 'display: none' })

        // Buttons
        $(urlOptions).attr({ 'style': 'display: none' })

        $(accessURL).attr({ 'onclick': "accessLink('" + string + "')" })
        $(accessURL).addClass('btn-primary')
        accessURL.innerHTML = "Access Link"
        // $(addTag).attr({ 'onclick': "cardEdit(" + UTubID + "," + URLID + ",'tag')" })
        $(editURL).attr({ 'onclick': "showInput('" + editURLid + "')" })
        $(delURL).attr({ 'onclick': "confirmModal('deleteURL')" })
        $(submit).attr({ 'onclick': "postData(event, '" + editURLid + "')" })
        // "/delete_url/" + UTubID + "/" + dictURLs[i].url_id
        delURL.innerHTML = "Delete"
    }

    editWrap2 = editWrap1;
    console.log(editWrap1)
    console.log(editWrap2)

    // Assemble url list items
    $(col).append(card);
    // $(card).append(cardImg); // incorporate a thumbnail of the URL to show when highlighted as the focus URL
    $(card).append(urlInfo);

    $(urlInfo).append(urlDescription);
    $(urlInfo).append(urlString);

    $(urlInfo).append(URLID == 0 ? editURLDescription : editWrap1);
    $(editWrap1).append(editURLDescription);
    $(urlInfo).append(URLID == 0 ? editURLString : editWrap2);
    $(editWrap2).append(editURLString);

    $(card).append(urlTags);
    $(card).append(urlOptions);
    $(urlOptions).append(accessURL);
    $(urlOptions).append(addTag);
    $(urlOptions).append(editURL);
    $(urlOptions).append(delURL);
    $(urlOptions).append(submit);

    return col;
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
            // Reorder createURL card to before selected URL
            var createCardCol = $('#createURL').detach();
            // console.log(createCardCol)
            createCardCol.appendTo('#URLFocusRow')

            // console.log($('#URLFocusRow').append($('#createURL').detach()));

            // console.log($('#URLFocusRow').children())
            // console.log($('#LWRRow').children())

            // Expand and highlight selected URL
            $('#URLFocusRow').append(cardCols[i]);
            $(cardCols[i]).toggleClass('col-lg-10 col-lg-4 col-xl-10 col-xl-3')
            card.addClass('selected')
            card.attr('draggable', '')
            card.find('.URLTags').show();
            card.find('.URLOptions').show();

            rowToggle = 0;
        } else {
            deselectURL($(cardCols[i]))
            activeRow.append(cardCols[i]);
        }

        activeRow = rowToggle ? $('#UPRRow') : $('#LWRRow');
    }
}

// Clear the URL Deck
function resetURLDeck() {
    // Empty URL Deck
    $('#UPRRow').empty();
    $('#URLFocusRow').empty();
    $('#LWRRow').empty();
}

function accessLink(url_string) {
    // Still need to implement: Take user to a new tab with interstitial page warning they are now leaving U4I
    if (!url_string.startsWith('https://')) {
        window.open('https://' + url_string, "_blank");
    } else {
        window.open(url_string, "_blank");
    }
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

            // Close modal
            $('#confirmModal').hide();
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