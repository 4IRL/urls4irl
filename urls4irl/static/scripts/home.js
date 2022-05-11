var currentUserID;
var selectedURL;

// UI Interactions
$(document).ready(function () {
    // Selected UTub
    var selectedUTubID;
    var selectedUTub;

    currentUserID = $('#welcome')[0].user_id;

    $('input:radio').click(function () {
        // Reset
        $('#TubImage').remove();

        radioButton = $('input[type=radio]:checked')[0];
        $('#UTubHeader')[0].innerHTML = radioButton.value;
        selectedUTubID = radioButton.id;
        $.getJSON('/home?UTubID=' + selectedUTubID, function (UTubJSON) {
            selectedUTub = UTubJSON;
            switchUTub(UTubJSON);
        });
    })

    // Selected URL
    $('#centerPanel').on('click', '#listURLs', function (e) {
        $(this).children().css("color", "black");    // Reset all to default color
        if ($(e.target)[0].style.color == 'black') {
            $(e.target).css("color", "yellow");      // Highlight new focus URL
        }

        var selectedURLid = $(e.target).attr("urlid");
        console.log(selectedURLid)
        var dictURLs = selectedUTub.urls;
        selectedURL = dictURLs.find(function (e) {
            if (e.url_id == selectedURLid) {
                return e
            }
        });
        selectURL(selectedUTubID);
    });

    // Selected Tag
    $('#TagDeck').on('click', '#listTags', function (e) {
        toggleTag($(e.target).parent().attr("tagid"));
    });

    // Selected User (only if creator)
    $('select').change(function () {
        // Update href
        $('#removeUserTemp').attr("action", '/remove_user/' + selectedUTubID + '/' + $(this)[0].value)
    })

    // Update UTub description (only if creator)
    $('#UTubInfo').addEventListener('input', function() {
        //handle update in db
    })

    // Update URL description
    $('#URLInfo').addEventListener('input', function() {
        //handle update in db
    })
});

// Functions

function switchUTub(selectedUTub) {

    console.log(selectedUTub)

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
            tagString += '<span tagid=' + tag.id + ' class="tag">' + tag.tag_string + '</span>';
        }

        // Assemble url list items
        html += '<li urlid=' + dictURLs[i].url_id + '>' + dictURLs[i].url_string + tagString + '</li>';
    }
    $('#listURLs')[0].innerHTML = html;
}

// Build LH panel tag list in selectedUTub
function buildTagDeck(dictTags) {
    let html = '';

    // // Tags are objects and need extracting/sorting based on keys
    // dictTags.sort(function (a, b) {
    //     if (a[0] > b[0]) {
    //         return 1
    //     } else {
    //         return -1
    //     }
    // });

    if (dictTags) {
        // Loop through all tags and provide checkbox input for filtering
        for (let i in dictTags) {
            let tagText = dictTags[i].tag_string;
            let tagID = dictTags[i].id;
            html += '<label for="' + tagText + '" tagid=' + tagID + '><input type="checkbox" name="' + tagText + '" checked>' + tagText + '</label>';
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
    $('#EditURL').attr("href", "/edit_url/" + selectedUTubID + "/" + selectedURLid);
    $('#DeleteURL').attr("href", "/delete_url/" + selectedUTubID + "/" + selectedURLid);
}

function toggleTag(tagID) {
    spanObjs = $('span[tagid="' + tagID + '"]')
    $($(spanObjs)).toggle()
    console.log($(spanObjs).parent().children())
    if ($(spanObjs).siblings().length < 1) {
        $($(spanObjs).parent()).toggle()
    }
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

function AccessLink() {
    if (!selectedURL.url_string.startsWith('https://')) {
        window.open('https://' + selectedURL.url_string, "_blank");
    } else {
        window.open(selectedURL.url_string, "_blank");
    }
}

// $.get('http://someurl.com',function(data,status) {
//       ...parse the data...
// },'html');