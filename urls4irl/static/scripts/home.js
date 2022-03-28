var selectedUTubID;
var selectedUTub;
var selectedURL;
var UserID;
var UTubJSON;
var tags;
var URLs = [];

function my_func(obj) {
    UTubJSON = obj;
    console.log(UTubJSON)
}

// UI Interactions

$(document).ready(function() {
    $('input:radio').click(function () {
        // Reset
        $('#TubImage').remove();
        $('#addURL').remove();
        $('#listURLs').parent()[0].innerHTML += '<a id="addURL" class="btn btn-success btn-sm mb-3 mx-3" href="#">Add a URL</a>';

        selectedUTubID = $('input[type=radio]:checked')[0].id;
        switchUTub(selectedUTubID);
        $('#UTubHeader')[0].innerHTML = $('input[type="radio"]:checked')[0].value;
    })

    $('select').change(function () {
        // Update href
        $('#removeUserTemp').attr("action", '/remove_user/' + selectedUTubID + '/' + $(this)[0].value)
    })


    $('#centerPanel').on('click','#listURLs', function (e) {
        $(this).children().css("color", "black");    // Reset all to default color
        $(e.target).css("color", "yellow");          // Highlight new focus URL
        let urlid = $(e.target).attr("urlid");

        selectedURL = $(e.target)[0].innerHTML;
        $('#DeleteURL').attr("href", "/delete_url/" + selectedUTubID + "/" + urlid);

        // Find notes for selected URL
        let i = 0;
        while (selectedUTub.urls[i].url.id != urlid) {
            i++;
        }
        $('#URLInfo')[0].innerHTML = selectedUTub.urls[i].notes;
    });
});

// Functions

function switchUTub(UTubID) {
    // Clear
    $('#URLInfo').innerHTML = '';

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
        for (let tag in tags) {
            tagString += '<span class="tag">' + tag + '</span>';
        }
        html += '<li urlid=' + url.id + '>' + url.url + tagString + '</li>';
    }
    $('#listURLs')[0].innerHTML = html;

    // Update UTub description
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

function AccessLink() {
    console.log(selectedURL)
    if(!selectedURL.startsWith('https://')) {
        window.open('https://' + selectedURL, "_blank");
    } else {
        window.open(selectedURL, "_blank");
    }
}

// $.get('http://someurl.com',function(data,status) {
//       ...parse the data...
// },'html');