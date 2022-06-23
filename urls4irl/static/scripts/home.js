var currentUserID;
var selectedURL;

// UI Interactions
$(document).ready(function () {
    // Selected UTub
    var selectedUTubID;
    var selectedUTub;
    var activeTagIDs;

    currentUserID = $('#welcome').attr('user_id');

    $('input:radio').click(function () {
        // Reset
        $('#TubImage').remove();

        radioButton = $('input[type=radio]:checked')[0];
        $('#UTubHeader')[0].innerHTML = radioButton.value;
        selectedUTubID = radioButton.id;
        $.getJSON('/home?UTubID=' + selectedUTubID, function (UTubJSON) {
            selectedUTub = UTubJSON;
            activeTagIDs = selectedUTub.tags.map(i => i.id);
            buildUTub(UTubJSON);
        });
    })

    // Selected URL
    $('#centerPanel').on('click', '#listURLs', function (e) {
        $(this).children().css("color", "black");    // Reset all to default color
        if ($(e.target)[0].style.color == 'black') {
            $(e.target).css("color", "blue");      // Highlight new focus URL
        }

        var selectedURLid = $(e.target).attr("urlid");
        var dictURLs = selectedUTub.urls;
        selectedURL = dictURLs.find(function (e) {
            if (e.url_id == selectedURLid) {
                return e
            }
        });

        selectURL(selectedUTubID);

        // // Attempt to avoid error when tag is clicked. Currently "children()" gives all children under ul#listURLs
        // console.log($(this).children().hasClass('url'))
        // if ($(this).children().hasClass('url')) {

        // }
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

function buildUTub(selectedUTub) {

    //Use local variables, pass them in to the subsequent functions as required
    var selectedUTubID = selectedUTub.id;
    var dictURLs = selectedUTub.urls;
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

    // Update hrefs
    $('#addURL').attr("href", "/add_url/" + selectedUTubID);
    $('#addUser').attr("href", "/add_user/" + selectedUTubID);
    $('#deleteUTubTemp').attr("action", "/delete_utub/" + selectedUTubID + "/" + currentUserID);
}

// Build center panel URL-tag list for selectedUTub
function buildURLDeck(dictURLs, dictTags) {
    let html = '';
    let cardHead = '<div class="col-md-12 col-lg-6 col-xl-4 mb-3"><div class="card"',
    cardInt1 = '><img class="card-img-top" src="..." alt="Card image cap"><div class="card-body"><h5 class="card-title">',
    cardInt2 = '</h5><p class="card-text">',
    cardInt3 = '</p></div></div></div>';
    
    for (let i in dictURLs) {
        // Build tag html strings 
        let tagArray = dictURLs[i].url_tags;
        let tagString = '';
        for (let j in tagArray) {
            let tag = dictTags.find(function (e) {
                if (e.id === tagArray[j]) {
                    return e.tag_string
                }
            });
            tagString += '<span class="tag" tagid="' + tag.id + '">' + tag.tag_string + '</span>';
        }

        // Assemble url list items
        html += cardHead + 'urlid="' + dictURLs[i].url_id + '" ' + cardInt1 + dictURLs[i].url_string + cardInt2 + tagString + cardInt3;
    }
    $('#listURLs')[0].innerHTML = html;
}

function updateURLDeck(activeTagIDs) {
    let urlList = $('li.url');
    for (let i = 0; i < urlList.length; i++) {
        // Default hide URL
        let hideURLBool = true;
        for (let j = 0; j < $(urlList[i])[0].children.length; j++) {
            // If at least one tag <span> for given url <li> exists in activeTagsIDs, negate default hide boolean (show URL)
            if (activeTagIDs.includes(parseInt($($(urlList[i])[0].children[j])[0].attributes.tagid.value))) {
                hideURLBool = false;
                break;
            }
        }
        // If url <li> has no tag <span>s in activeTagIDs, hide <li>
        if (hideURLBool) { $(urlList[i]).hide(); }
        // If tag reactivated, show URL
        else { $(urlList[i]).show(); }
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

function selectURL(selectedUTubID) {
    // Find notes for selected URL
    $('#URLInfo')[0].innerHTML = selectedURL.notes;
    var selectedURLid = selectedURL.url_id;

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