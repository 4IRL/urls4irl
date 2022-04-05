var dictUTubs = [];         // Array with all UTubs for currentUser
var selectedUTub = {};      // Object with all relevant data for a single UTub
var selectedUTubID;         // Current UTub ID
var dictURLs = [];          // Array of all URLs in selectedUTub
var dictTags = [];          // Array of all tags in selectedUTub
var dictMembers = [];       // Array of all members in selectedUTub
var currentUserID;
var selectedURL = {         // Used to identify which URL is in focus
    url: '',
    id: 0
};

function my_func(UTubs) {
    dictUTubs = UTubs;
    console.log(dictUTubs)
}

// UI Interactions
$(document).ready(function () {
    // Selected UTub
    $('input:radio').click(function () {
        // Reset
        $('#TubImage').remove();

        radioButton = $('input[type=radio]:checked')[0];
        $('#UTubHeader')[0].innerHTML = radioButton.value;
        selectedUTubID = radioButton.id;
        $.getJSON('/home?UTubID=' + selectedUTubID, function(UTubJSON) {
            console.log('/home?UTubID=' + selectedUTubID)
            selectedUTub = UTubJSON;
            dictURLs = selectedUTub.urls;
            dictTags = selectedUTub.tags;
            dictUsers = selectedUTub.members;
    
            switchUTub();
        });

    })

    // Selected URL
    $('#centerPanel').on('click', '#listURLs', function (e) {
        $(this).children().css("color", "black");    // Reset all to default color
        $(e.target).css("color", "yellow");          // Highlight new focus URL

        selectedURL.url = $(e.target)[0].innerHTML;
        selectedURL.id = $(e.target).attr("urlid");
        selectURL(selectedURL);
    });

    // Selected Tag
    $('#TagDeck').on('click', '#listTags', function (e) {
        toggleTag($(e.target).parent().attr("tagid"));
    });

    // Selected User
    $('select').change(function () {
        // Update href
        $('#removeUserTemp').attr("action", '/remove_user/' + selectedUTubID + '/' + $(this)[0].value)
    })
});

// Functions

function switchUTub() {
    // Clear 
    resetUTubs();

    // Center panel
    buildURLDeck();

    // LH panels
    buildTagDeck();

    // RH panels
    // Update UTub description, not yet implemented on backend
    // $('#UTubInfo')[0].innerHTML = selectedUTub.description;

    gatherUsers();

    // Update hrefs
    $('#addURL').attr("href", "/add_url/" + selectedUTubID);
    $('#addUser').attr("href", "/add_user/" + selectedUTubID);
    $('#deleteUTubTemp').attr("action", "/delete_utub/" + selectedUTubID + "/" + selectedUTub.creator);
}

// Build LH panel tag list in selectedUTub
function buildTagDeck() {
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

function toggleTag(tagID) {
    spanObjs = $('span[tagid="' + tagID + '"]')
    $($(spanObjs).parent()).toggle()
}

// Build center panel URL-tag list for selectedUTub
function buildURLDeck() {
    let html = '';
    for (let i in dictURLs) {
        // Build tag html strings 
        let tagArray = dictURLs[i].url_tags;
        let tagString = '';
        for (let j in tagArray) {
            let tag = dictTags.find(e => e.id === tagArray[j]);
            tagString += '<span tagid=' + tag.id + ' class="tag">' + tag.tag_string + '</span>';
        }

        // Assemble url list items
        html += '<li urlid=' + dictURLs[i].id + '>' + dictURLs[i].url_string + tagString + '</li>';
    }
    $('#listURLs')[0].innerHTML = html;
}

function selectURL(urlObj) {
    // Find notes for selected URL
    let i = 0;
    while (selectedUTub.urls[i].url.id != urlObj.id) {
        i++;
    }
    $('#URLInfo')[0].innerHTML = selectedUTub.urls[i].notes;

    // Update hrefs
    $('#addTags').attr("href", "/add_tag/" + selectedUTubID + "/" + selectedURL.id);
    $('#EditURL').attr("href", "/edit_url/" + selectedUTubID + "/" + selectedURL.id);
    $('#DeleteURL').attr("href", "/delete_url/" + selectedUTubID + "/" + selectedURL.id);
}

// Creates option dropdown menu of users in RH UTub information panel
function gatherUsers() {
    UserArray = selectedUTub.users;
    html = '<option disabled selected value> -- Select a User -- </option>';
    for (let i in UserArray) {
        let user = UserArray[i];
        if (user.id == selectedUTub.creator) {
            $('#UTubOwner')[0].innerHTML = user.username;
        } else {
            html += '<option value=' + user.id + '>' + user.username + '</option>'
        }
    }
    $('#UTubUsers')[0].innerHTML = html;
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
    if (!selectedURL.url.startsWith('https://')) {
        window.open('https://' + selectedURL.url, "_blank");
    } else {
        window.open(selectedURL.url, "_blank");
    }
}

// $.get('http://someurl.com',function(data,status) {
//       ...parse the data...
// },'html');