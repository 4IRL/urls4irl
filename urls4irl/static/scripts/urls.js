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
    console.log($('.url.selected').last().attr('urlid'))
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
    let urlInfo = document.createElement(URLID == 0 ? 'form' : 'div');
    let urlDescriptionWrap = document.createElement('label');
    let urlDescription = document.createElement(URLID == 0 ? 'input' : 'h5');
    let urlStringWrap = document.createElement('label');
    let urlString = document.createElement(URLID == 0 ? 'input' : 'p');
    let urlTags = document.createElement('div');
    let urlOptions = document.createElement('div');
    let accessURL = document.createElement('button');
    let addTag = document.createElement('button');
    let editURL = document.createElement('button');
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

    $(urlDescriptionWrap).attr({
        'for': 'newURLDescription'
    })

    $(urlDescription).attr({ 'class': 'card-title' })

    $(urlStringWrap).attr({
        'for': 'newURL'
    })

    $(urlString).attr({ 'class': 'card-text' })

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
        'class': 'card-link btn btn-warning',
        'type': 'button'
    })
    editURL.innerHTML = "Edit"

    $(delURL).attr({
        'class': 'card-link btn btn-danger',
        'type': 'button'
    })

    // Creation URL specific items
    if (URLID == 0) {
        // New URL card and input text fields. Initially hidden, shown when create URL is requested. Input field recreated here to ensure at the end of list after creation of new URL
        $(col).attr({
            'id': 'createURL',
            'class': 'createDiv',
            'style': 'display: none',
            'onblur': 'hideInput(event)'
        })
        $(col).addClass('col-lg-10 col-xl-10')

        $(card).addClass('selected')

        $(urlDescription).attr({
            'type': 'text',
            'id': 'newURLDescription',
            'placeholder': 'New URL description',
            'size': '50'
        })
        $(col).addClass('userInput')

        $(urlString).attr({
            'type': 'text',
            'id': 'newURL',
            'placeholder': 'New URL',
            'size': '50'
        })
        $(urlString).addClass('userInput')

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

        urlDescription.innerHTML = description ? description : ''
        urlString.innerHTML = string;

        $(urlTags).attr({ 'style': 'display: none' })

        // Buttons
        $(urlOptions).attr({ 'style': 'display: none' })

        $(accessURL).attr({ 'onclick': "accessLink('" + string + "')" })
        $(accessURL).addClass('btn-primary')
        accessURL.innerHTML = "Access Link"
        // $(addTag).attr({ 'onclick': "cardEdit(" + UTubID + "," + URLID + ",'tag')" })
        $(editURL).attr({ 'onclick': "cardEdit(" + UTubID + "," + URLID + ",'url')" })
        $(delURL).attr({ 'onclick': "deleteURL()" })
        // "/delete_url/" + UTubID + "/" + dictURLs[i].url_id
        delURL.innerHTML = "Delete"
    }

    // Assemble url list items
    $(col).append(card);
    // $(card).append(cardImg);
    $(card).append(urlInfo);
    $(urlDescriptionWrap).append(urlDescription);
    $(urlInfo).append(URLID == 0 ? urlDescriptionWrap : urlDescription);
    $(urlStringWrap).append(urlString);
    $(urlInfo).append(URLID == 0 ? urlStringWrap : urlString);
    $(card).append(urlTags);
    $(card).append(urlOptions);
    $(urlOptions).append(accessURL);
    $(urlOptions).append(addTag);
    $(urlOptions).append(editURL);
    $(urlOptions).append(delURL);

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
    console.log($('#LWRRow').children())
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