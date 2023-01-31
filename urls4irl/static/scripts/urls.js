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
    console.log($('.url.selected').attr('urlid'))
    return $('.url.selected').attr('urlid');
}

// Build center panel URL-tag list for selectedUTub
function buildURLDeck(dictURLs, dictTags) {

    $('#editUTubButton').show();
    $('#addURL').show();
    $('#UTubDescription').show();

    for (let i in dictURLs) {

        var URLcol = createURL(dictURLs[i].url_id, dictURLs[i].url_string, dictURLs[i].url_description, dictURLs[i].url_tags,dictTags)

        UPRRow.append(URLcol);
    }

    // New URL card and input text fields. Initially hidden, shown when create URL is requested. Input field recreated here to ensure at the end of list after creation of new URL
    let col = document.createElement('div');
    let card = document.createElement('div');
    let urlInfo = document.createElement('form');
    let urlDescriptionWrap = document.createElement('label');
    let urlDescription = document.createElement('input');
    let urlStringWrap = document.createElement('label');
    let urlString = document.createElement('input');
    let urlTags = document.createElement('div');
    let urlOptions = document.createElement('div');
    let accessURL = document.createElement('button');
    let addTag = document.createElement('button');
    let editURL = document.createElement('button');
    let delURL = document.createElement('button');

    $(col).attr({
        'id': 'createURL',
        'class': 'cardCol mb-3 col-md-10 col-lg-10 col-xl-10',
        'style': 'display: none',
        'onblur': 'hideInput(event)'
    })

    $(card).attr({
        'class': 'card url selected',
        'draggable': 'true',
        'ondrop': 'dropIt(event)',
        'ondragover': 'allowDrop(event)',
        'ondragstart': 'dragStart(event)'
    })

    $(urlInfo).attr({ 'class': 'card-body URLInfo' })

    $(urlDescriptionWrap).attr({
        'for': 'newURLDescription'
    })

    $(urlDescription).attr({
        'type': 'text',
        'id': 'newURLDescription',
        'class': 'userInput card-title',
        'placeholder': 'New URL description',
        'size': '30'
    })

    $(urlStringWrap).attr({
        'for': 'newURL'
    })

    $(urlString).attr({
        'type': 'text',
        'id': 'newURL',
        'class': 'userInput card-text',
        'placeholder': 'New URL',
        'size': '30'
    })

    $(urlTags).attr({ 'class': 'card-body URLTags' })

    $(urlOptions).attr({ 'class': 'card-body URLOptions' })

    $(accessURL).attr({
        'class': 'card-link btn btn-success',
        'type': 'button',
        'onclick': 'postData(event, "createURL")'
    })
    accessURL.innerHTML = "Create URL"

    $(addTag).attr({
        'class': 'card-link btn btn-info',
        'type': 'button',
        // 'onclick': "showInput('addTag')"
        // 'onclick': "cardEdit(" + selectedUTubID + "," + dictURLs[i].url_id + ",'tag')" want to be able to add tags for addition before verification
    })
    addTag.innerHTML = "Add Tag"

    $(editURL).attr({
        'class': 'card-link btn btn-warning',
        'type': 'button',
        // 'onclick': "cardEdit(" + selectedUTubID + "," + dictURLs[i].url_id + ",'url')" should refocus on URL input
        // 'onclick': "(function(){ alert('Hey i am calling'); return false; })();return false;"
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
    $(card).append(urlInfo);
    $(urlDescriptionWrap).append(urlDescription);
    $(urlInfo).append(urlDescriptionWrap);
    $(urlStringWrap).append(urlString);
    $(urlInfo).append(urlStringWrap);
    $(card).append(urlTags);
    $(card).append(urlOptions);
    $(urlOptions).append(accessURL);
    $(urlOptions).append(addTag);
    $(urlOptions).append(editURL);
    $(urlOptions).append(delURL);

    URLFocusRow.append(col);
}

// Add a URL to current UTub
function createURL(URLID, URLString, URLDescription, URLTags, dictTags) {
    
    let selectedUTubID = currentUTubID();
    
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
    urlDescription.innerHTML = URLDescription ? URLDescription : ''

    $(urlString).attr({ 'class': 'card-text' })
    urlString.innerHTML = URLString;

    $(urlTags).attr({ 'class': 'card-body URLTags', 'style': 'display: none' })

    // Build tag html strings 
    let tagArray = URLTags;
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
            'class': 'btn btn-sm btn-outline-link border-0 tag-remove',
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
        'onclick': "accessLink('" + URLString + "')"
    })
    accessURL.innerHTML = "Access Link"

    $(addTag).attr({
        'class': 'card-link btn btn-info',
        'type': 'button',
        // 'onclick': "showInput('addTag')"
        'onclick': "cardEdit(" + selectedUTubID + "," + URLID + ",'tag')"
    })
    addTag.innerHTML = "Add Tag"

    $(editURL).attr({
        'class': 'card-link btn btn-warning',
        'type': 'button',
        'onclick': "cardEdit(" + selectedUTubID + "," + URLID + ",'url')"
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

    return col;
    
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

            // Reorder create URL card to before selected URL
            $('#createURL').detach();
            activeRow.append($('#createURL'));

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
        window.open('https://' + selectedURL.url_string, "_blank");
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