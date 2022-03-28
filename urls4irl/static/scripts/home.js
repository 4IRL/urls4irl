var selectedUTubID;
var selectedUTub;
var selectedURL = {
    url: '',
    id: 0
};
var UserID;
var UTubJSON;
var tags;
var URLs = [];

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

    // Selected User
    $('select').change(function () {
        // Update href
        $('#removeUserTemp').attr("action", '/remove_user/' + selectedUTubID + '/' + $(this)[0].value)
    })
});

// Functions

function switchUTub(UTubID) {
    // Clear 
    clearSelectedURL()

    // Loop through array to find selected UTub
    let i = 0;
    while (UTubJSON[i].id != UTubID) {
        i++;
    }
    selectedUTub = UTubJSON[i];

    // Build center panel URL-tag list
    URLArray = selectedUTub.urls;
    let html = '';
    for (let i in URLArray) {
        let url = URLArray[i].url;
        URLs.push(url);
        let tags = URLArray[i].tags;
        let tagString = '';
        console.log(tags)
        for (let i in tags) {
            tagString += '<span class="tag">' + tags[i].tag + '</span>';
        }
        html += '<li urlid=' + url.id + '>' + url.url + tagString + '</li>';
    }
    $('#listURLs')[0].innerHTML = html;

    // Update UTub description, not yet implemented on backend
    // $('#UTubInfo')[0].innerHTML = selectedUTub.description;

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

    // Update hrefs
    $('#addURL').attr("href", "/add_url/" + UTubID);
    $('#addUser').attr("href", "/add_user/" + UTubID);
    $('#deleteUTubTemp').attr("action", "/delete_utub/" + UTubID + "/" + selectedUTub.creator);
}

function selectURL(selectedURL) {
    // Find notes for selected URL
    let i = 0;
    while (selectedUTub.urls[i].url.id != selectedURL.id) {
        i++;
    }
    $('#URLInfo')[0].innerHTML = selectedUTub.urls[i].notes;
    
    // Update hrefs
    $('#addTags').attr("href", "/add_tag/" + selectedUTubID + "/" + selectedURL.id);
    $('#EditURL').attr("href", "/edit_url/" + selectedUTubID + "/" + selectedURL.id);
    $('#DeleteURL').attr("href", "/delete_url/" + selectedUTubID + "/" + selectedURL.id);
}

function clearSelectedURL() {
    $('#URLInfo')[0].innerHTML = '';
    
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