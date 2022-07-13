// UI Interactions
$(document).ready(function() {

    // Instantiate UTubDeck with user's accessible UTubs
    radioHTML = '';
    for (i in UTubs) {
        radioHTML += '<label for="UTub' + UTubs[i].id + '"><input type="radio" id="UTub' + UTubs[i].id + '" name="UTubSelection" value="' + UTubs[i].name + '">' + UTubs[i].name + '</label>';
    }
    $('#UTubDeck').find('form')[0].innerHTML = radioHTML;

    // User selected a UTub, display data
    $('input[type=radio]').on('click', function() {
        // Reset
        $('#TubImage').remove();

        // Find which UTub was requested
        let selectedUTubID = findUTubID();

        // Pull data from db
        $.getJSON('/home?UTubID=' + selectedUTubID, function(UTubJSON) { buildUTub(UTubJSON) });
    })

    // Selected URL
    $('#centerPanel').on('click', function (e) {
        var selectedCard = $(e.target).closest('div.card');
        if (selectedCard.hasClass("selected")) {    // Already selected, user would like to unselect
            selectedCard.removeClass("selected");
        } else {                                    // Unselected, user would like to select a different URL
            $('#centerPanel').find('div.card').removeClass("selected");
            selectedCard.addClass("selected");
        }
        console.log(selectedCard.attr("urlid"))

        selectURL();
    });

    // Selected Tag
    $('#TagDeck').on('click', '#listTags', function (e) {
        let clickedTagID;

        // Handle checkbox display
        if (e.target.nodeName.toLowerCase() == 'label') {
            // Label clicked. Also toggles checkbox and assigns clickedTagID
            let input = $(e.target).children();
            input.prop("checked", !input.prop("checked"));
            clickedTagID = $(e.target).attr("tagid");
        } else {
            // Checkbox clicked. Default functionality
            clickedTagID = $(e.target).parent().attr("tagid")
        }
        clickedTagID = parseInt(clickedTagID);

        // Hide/Show corresponding tag span
        spanObjs = $('span[tagid="' + clickedTagID + '"]')
        $($(spanObjs)).toggle()

        // If unchecked, remove from activeTagIDs. Else, tag was checked and needs to be readded to activeTagIDs
        const i = activeTagIDs.indexOf(clickedTagID);
        if (i > -1) {
            activeTagIDs.splice(i, 1);
        } else {
            activeTagIDs.push(clickedTagID)
        }

        updateURLDeck(activeTagIDs);
    });

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
    radioButton = $('input[type=radio]:checked')[0];
    $('#UTubHeader')[0].innerHTML = radioButton.value;
    str = radioButton.id;
    return str.charAt(str.length - 1);
}

function dictURLs() {
    let URLs = $('#listURLs').find('.card-title').map(i => i.innerHTML)
    return 1
}

function dictURLs() {
    return $('#listURLs').find('.card-title').map(i => i.innerHTML)
}

function buildUTub(selectedUTub) {

    //Use local variables, pass them in to the subsequent functions as required
    var selectedUTubID = selectedUTub.id;
    var dictURLs = selectedUTub.urls;
    console.log(dictURLs)
    var dictTags = selectedUTub.tags;
    var dictUsers = selectedUTub.members;
    var creator = selectedUTub.created_by;

    // Clear 
    resetUTubs();

    // Center panel
    buildURLDeck(dictURLs, dictTags);

    // LH panels
    buildTagDeck(dictTags);

    // RH panels
    // Update UTub description, not yet implemented on backend
    // $('#UTubInfo')[0].innerHTML = selectedUTub.description;

    gatherUsers(dictUsers, creator);

    let currentUserID = $('#welcome').attr('user_id');

    // Update hrefs
    $('#addURL').attr("href", "/add_url/" + selectedUTubID);
    $('#addUser').attr("href", "/add_user/" + selectedUTubID);
    $('#deleteUTubTemp').attr("action", "/delete_utub/" + selectedUTubID + "/" + currentUserID);
}

// Build center panel URL-tag list for selectedUTub
function buildURLDeck(dictURLs, dictTags) {
    let card = document.createElement('div');
    setAttributes(card, { "id": "-group", "class": "board-list", "ondrop": "dropIt(event)", "ondragover": "allowDrop(event)", "ondragstart": "dragStart(event)" });

    let html = '';
    let cardHead = '<div class="col-md-12 col-lg-4 col-xl-3 mb-3"><div class="card url" draggable="true"',
        cardInt1 = '><img class="card-img-top" src="..." alt="Card image cap">', // Potential option to show static image preview of destination site
        cardInt2 = '><div class="card-body"><h5 class="card-title">',
        cardInt3 = '</h5><p class="card-text">',
        cardInt4 = '</p></div></div></div>';

    for (let i in dictURLs) {
        // Build tag html strings 
        let tagArray = dictURLs[i].url_tags;
        let tagString = '';
        for (let j in tagArray) { // Find applicable tags in dictionary to apply to URL card
            let tag = dictTags.find(function (e) {
                if (e.id === tagArray[j]) {
                    return e.tag_string
                }
            });
            tagString += '<span class="tag" tagid="' + tag.id + '">' + tag.tag_string + '</span>';
        }

        // Assemble url list items
        html += cardHead + 'urlid="' + dictURLs[i].url_id + '" ' + cardInt2 + dictURLs[i].url_string + cardInt3 + tagString + cardInt4;
    }
    card.innerHTML = html;

    // $("#boardlists")[0].insertBefore(card, $("#boardlists")[0].firstChild);

    $('#listURLs')[0].innerHTML = html;
}

function updateURLDeck(activeTagIDs) {
    let urlList = $('div.url');
    console.log(activeTagIDs)
    for (let i = 0; i < urlList.length; i++) {
        // Default hide URL
        let hideURLBool = true; // Default boolean (hide URL)
        for (let j = 0; j < $(urlList[i])[0].children.length; j++) {
            // If at least one tag <span> for given url <div.card.url> exists in activeTagsIDs, negate default boolean (show URL)
            console.log(parseInt($($(urlList[i])[0].children[j]).find('span.tag').attr('tagid')))
            if (activeTagIDs.includes(parseInt($($(urlList[i])[0].children[j]).find('span.tag').attr('tagid')))) {
                hideURLBool = false;
            }
        }
        console.log(i)
        console.log(hideURLBool)
        // If url <div.card.url> has no tag <span>s in activeTagIDs, hide card column (so other cards shift into its position)
        if (hideURLBool) { $(urlList[i]).parent().hide(); }
        // If tag reactivated, show URL
        else { $(urlList[i]).parent().show(); }
    }
}

// Build LH panel tag list in selectedUTub
function buildTagDeck(dictTags) {
    let html = '<label for="selectAll"><input id="selectAll" type="checkbox" name="selectAll" checked> Select All </label>';

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

    if (dictTags) {
        // Loop through all tags and provide checkbox input for filtering
        for (let i in dictTags) {
            let tagText = dictTags[i].tag_string;
            let tagID = dictTags[i].id;
            html += '<label for="' + tagText + '" tagid=' + tagID + '><input class="tagCheckbox" type="checkbox" name="' + tagText + '" checked> ' + tagText + ' </label>';
        }
    } else {
        html += '<h5>No Tags Applied to any URLs in this UTub</h5>'     // No tags in UTub
    }
    $('#listTags')[0].innerHTML = html
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

function selectURL() {
    // Find notes for selected URL
    $('#URLInfo')[0].innerHTML = selectedURL.notes;
    var selectedURLid = selectedURL.url_id;
    let selectedUTubID = findUTubID();

    // Update hrefs
    $('#addTags').attr("href", "/add_tag/" + selectedUTubID + "/" + selectedURLid);
    $('#EditURL').attr("onclick", "editURL(" + selectedUTubID + "," + selectedURLid + ")");
    $('#DeleteURL').attr("href", "/delete_url/" + selectedUTubID + "/" + selectedURLid);
}

function resetUTubs() {
    // Reset tag deck
    tags = [];

    // Empty URL description
    $('#URLInfo')[0].innerHTML = '';

    // Empty TagsDeck
    $('#listTags')[0].innerHTML = '';
    tagsObj = {};

    // Update hrefs
    $('#addTags').attr("href", "#");
    $('#EditURL').attr("href", "#");
    $('#DeleteURL').attr("href", "#");
}

function accessLink() {
    if (!selectedURL.url_string.startsWith('https://')) {
        window.open('https://' + selectedURL.url_string, "_blank");
    } else {
        window.open(selectedURL.url_string, "_blank");
    }
}

function editURL(selectedUTubID, selectedURLid) {
    var URLli = "li[urlid=" + selectedURLid + "]";   // Find URL HTML with selected ID
    var liHTML = $(URLli).html().split('<span');     // Store pre-edit values
    var URLString = liHTML[0];
    var tags = liHTML.slice(1);
    tags = tags.map(i => '<span' + i)
    var tagString = liHTML.slice(1).map(i => '<span' + i).join('');

    $(URLli).html('');                               // Clear li
    $('<input></input>').attr({                      // Replace with temporary input
        'type': 'text',
        'id': 'edit_url',
        'urlid': selectedURLid,
        'size': '30',
        'value': URLString
    }).appendTo($(URLli));
    $(URLli).html($(URLli).html() + tagString);
    $('#edit_url').focus();

    $(document).on("blur", '#edit_url', function () {
        var urlText = $(this).val();
        var selectedURLid = $(this).attr('urlid');
        let request = $.ajax({
            type: 'post',
            url: "/edit_url/" + selectedUTubID + "/" + selectedURLid
        });
        console.log($('#edit_url'))
        request.done(function (response, textStatus, xhr) {
            if (xhr.status == 200) {
            }
        }
        )
    });
}