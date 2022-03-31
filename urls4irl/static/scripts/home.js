var UTubJSON;               // Full JSON sent from server
var URLs = [];              // Array with all URL data sent from server in the selectedUTub
var tagsObj = {};           // Object with tag key and id value pairs
var UserID;
var selectedUTub;           // Array item for the current UTub
var selectedUTubID;         // Current UTub ID
var selectedURL = {         // Used to identify which URL is in focus
    url: '',
    id: 0
};

function my_func(obj) {
    UTubJSON = obj;
    console.log(UTubJSON)
}

// UI Interactions

$(document).ready(function () {
    // Selected UTub
    $('input:radio').click(function () {
        // Reset
        $('#TubImage').remove();
        $('#addURL').remove();
        $('#listURLs').parent()[0].innerHTML += '<a id="addURL" class="btn btn-success btn-sm mb-3 mx-3" href="#">Add a URL</a>';

        selectedUTubID = $('input[type=radio]:checked')[0].id;
        switchUTub(selectedUTubID);
        $('#UTubHeader')[0].innerHTML = $('input[type="radio"]:checked')[0].value;
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

function switchUTub(UTubID) {
    // Clear 
    resetUTubs();

    // Loop through array to find selected UTub
    let i = 0;
    while (UTubJSON[i].id != UTubID) {
        i++;
    }
    selectedUTub = UTubJSON[i];

    // Center panel
    buildURLDeck();

    // LH panels
    buildTagDeck();

    // RH panels
    // Update UTub description, not yet implemented on backend
    // $('#UTubInfo')[0].innerHTML = selectedUTub.description;

    gatherUsers();

    // Update hrefs
    $('#addURL').attr("href", "/add_url/" + UTubID);
    $('#addUser').attr("href", "/add_user/" + UTubID);
    $('#deleteUTubTemp').attr("action", "/delete_utub/" + UTubID + "/" + selectedUTub.creator);
}

// Build LH panel tag list in selectedUTub
function buildTagDeck() {
    let html = '';
    // Tags are objects and need extracting/sorting based on keys
    let tagEntries = Object.entries(tagsObj)
    tagEntries.sort(function (a, b) {
        if (a[0] > b[0]) {
            return 1
        } else {
            return -1
        }
    });

    if (tagEntries.length !== 0) {
        // Loop through all tags and provide checkbox input for filtering
        for (let i in tagEntries) {
            let tagText = tagEntries[i][0]
            let tagID = tagEntries[i][1]
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
    URLArray = selectedUTub.urls;
    let html = '';
    let tagText = [];                                       // A placeholder to check for unique tags to be added to global tags array
    for (let i in URLArray) {
        // Load URLs on frontend array
        let urlItem = URLArray[i];

        // Build tag html strings 
        let tagString = '';
        for (let j in urlItem.tags) {
            let tagItem = urlItem.tags[j];
            // Extract all tags in UTub
            if (tagText.indexOf(tagItem.tag) === -1) {
                tagText.push(tagItem.tag);
                tagsObj[tagItem.tag] = tagItem.id;
            }
            tagString += '<span tagid=' + tagItem.id + ' class="tag">' + tagItem.tag + '</span>';
        }

        // Assemble url list items
        html += '<li urlid=' + urlItem.url.id + '>' + urlItem.url.url + tagString + '</li>';
    }
    $('#listURLs')[0].innerHTML = html;
}

function selectURL(urlItem) {
    // Find notes for selected URL
    let i = 0;
    while (selectedUTub.urls[i].url.id != urlItem.id) {
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