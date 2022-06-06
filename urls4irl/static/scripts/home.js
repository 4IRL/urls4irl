var currentUserID;
var selectedURL;

// UI Interactions
$(document).ready(function () {
    // Selected UTub
    var selectedUTubID;
    var selectedUTub;
    var activeTags;

    currentUserID = $('#welcome')[0].user_id;

    $('input:radio').click(function () {
        // Reset
        $('#TubImage').remove();

        radioButton = $('input[type=radio]:checked')[0];
        $('#UTubHeader')[0].innerHTML = radioButton.value;
        selectedUTubID = radioButton.id;
        $.getJSON('/home?UTubID=' + selectedUTubID, function (UTubJSON) {
            selectedUTub = UTubJSON;
            activeTags = selectedUTub.tags;
            buildUTub(UTubJSON);
        });
    })

    // Selected URL
    $('#centerPanel').on('click', '#listURLs', function (e) {
        $(this).children().css("color", "black");    // Reset all to default color
        if ($(e.target)[0].style.color == 'black') {
            $(e.target).css("color", "yellow");      // Highlight new focus URL
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

        // Label clicked. Also toggles checkbox and assigns clickedTagID
        if (e.target.nodeName.toLowerCase() == 'label') {
            let input = $(e.target).children();
            input.prop("checked", !input.prop("checked"));
            clickedTagID = $(e.target).attr("tagid");
            console.log(activeTags)
        } else { // Checkbox clicked
            clickedTagID = $(e.target).parent().attr("tagid")
        }

        updateURLDeck(activeTags);
    });

    
    $('#edit_url').on( "blur", function () {
        console.log("reached the blur")
        var urlText = $(this).val();
        var selectedURLid = $(this).attr('urlid');
        $.ajax({
            type: 'post',
            url: "/edit_url/" + selectedUTubID + "/" + selectedURLid,
            success: function () {
                $('#edit_url').text(urlText);
            }
        });
    });

    // // Change url to text input for edit
    // $('li.url').click(function () {
    //     console.log(selectedURL)
    //     var urlid = $(this).attr('urlid');
    //     var urlText = $(this).text();
    //     $(this).html('');
    //     $('<input></input>')
    //         .attr({
    //             'type': 'text',
    //             'id': 'edit_url',
    //             'urlid': urlid,
    //             'size': '30',
    //             'value': urlText
    //         })
    //         .appendTo(this);
    //     $('#edit_url').focus();
    // });

    //    // Accept and POST changes to url once focus shifted
    //    $('li.url').on('blur','#edit_url', function(){
    //     var urlText = $(this).val();
    //     $.ajax({
    //       type: 'post',
    //       url: '/edit_url' + urlText,
    //       success: function(){
    //         $('#edit_url').text(urlText);
    //       }
    //     });

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
        html += '<li class="url" urlid="' + dictURLs[i].url_id + '">' + dictURLs[i].url_string + tagString + '</li>';
    }
    $('#listURLs')[0].innerHTML = html;
}

function updateURLDeck(activeTags) {
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
    $('#EditURL').attr("onclick", "EditURL(" + selectedURLid + ")");
    $('#DeleteURL').attr("href", "/delete_url/" + selectedUTubID + "/" + selectedURLid);
}

function toggleTag(tagID) {
    spanObjs = $('span[tagid="' + tagID + '"]')
    $($(spanObjs)).toggle()
    let sibArray = $(spanObjs).siblings();
    for (let i = 0; i < sibArray.length; i++) {
        console.log(sibArray[i].innerHTML)
    }
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

function EditURL(selectedURLid) {
    var URLli = $("li[urlid=" + selectedURLid + "]");   // Find URL HTML with selected ID
    var liHTML = URLli.html().split('<span');           // Store pre-edit values
    var URLString = liHTML[0];
    var tagString = '<span' + liHTML[1];
    
    URLli.html('');                                     // Clear li
    $('<input></input>').attr({                         // Replace with temporary input
            'type': 'text',
            'id': 'edit_url',
            'urlid': selectedURLid,
            'size': '30',
            'value': URLString
        }).appendTo(URLli);
    $('#edit_url').focus();
}

// $.get('http://someurl.com',function(data,status) {
//       ...parse the data...
// },'html');