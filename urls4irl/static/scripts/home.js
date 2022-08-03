// UI Interactions
$(document).ready(function () {

    // Instantiate UTubDeck with user's accessible UTubs
    buildUTubDeck(UTubs);

    // User selected a UTub, display data
    $('input[type=radio]').on('click', function () {

        $('.active').toggleClass('active');
        console.log($('.active'))
        $(this).parent().toggleClass('active');

        getUtubInfo(findUTubID());
    })

    // Selected URL
    $('#centerPanel').on('click', function (e) {
        if (e.target.localName === 'i') {
            let card = $(e.target).closest('.card');
            let deleteURLID = card.attr('urlid');
            let request = $.ajax({
                type: 'post',
                url: "/delete_url/" + findUTubID() + "/" + deleteURLID
            });

            request.done(function (response, textStatus, xhr) {
                if (xhr.status == 200) {
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
                console.log("Error: " + error);
            })
            card.fadeOut();
            card.remove();
        } else {
            var selectedCard = $(e.target).closest('div.card');
            if (selectedCard.hasClass("selected")) {    // Already selected, user would like to unselect
                selectedCard.removeClass("selected");
                $('.close-icon').hide();
            } else {                                    // Unselected, user would like to select a different URL
                $('#centerPanel').find('div.card').removeClass("selected");
                $('.close-icon').hide();
                selectedCard.addClass("selected");
                selectedCard.find('.close-icon').show();
            }

            var selectedURLid = selectedCard.attr("urlid")

            selectURL(selectedURLid);
        }
    });

    $('.close-icon').on('click', function () {
    })

    // Selected Tag
    $('#TagDeck').on('click', function (e) {
        let label;
        let input;
        let clickedTagID;
        if (e.target.nodeName.toLowerCase() == 'label') {
            // Label clicked. Reset input var. Also toggles checkbox and assigns clickedTagID
            label = $(e.target);
            input = label.children();
            input.prop("checked", !input.prop("checked"));
        } else {
            // Input clicked. Already toggles checkbox
            input = $(e.target);
            label = input.parent();
        }

        if (input[0].id == 'selectAll') {

            if (e.target.nodeName.toLowerCase() == 'label') {
                e.preventDefault();
            }

            // Toggle all filter tags
            $('input[type=checkbox]').prop("checked", input[0].checked);

            // Hide/Show all tag spans
            spanObjs = $('span.tag')
            if (input[0].checked) {
                $($(spanObjs)).show()
            } else {
                $($(spanObjs)).hide()
            }
        } else {

            let selectAllBool = true;
            $('input[type=checkbox]').each(function (i) {
                if (i !== 0) {
                    selectAllBool &= $(this).prop("checked");
                }
            })

            $('#selectAll').prop("checked", selectAllBool);

            clickedTagID = parseInt(label.attr("tagid"));

            // Hide/Show corresponding tag span
            spanObjs = $('span[tagid="' + clickedTagID + '"]')
            $($(spanObjs)).toggle()
        }

        // Update URLs displayed as a result of checkbox filtering
        updateURLDeck();
    });

    // Listen for click on toggle checkbox
    $('#selectAll').click(function (event) {
        if (this.checked) {
            // Iterate each checkbox
            $(':checkbox').each(function () {
                this.checked = true;
            });
        } else {
            $(':checkbox').each(function () {
                this.checked = false;
            });
        }
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

function buildUTubDeck(UTubs) {
    // Instantiate UTubDeck with user's accessible UTubs
    radioHTML = '';
    for (i in UTubs) {
        radioHTML += '<label for="UTub-' + UTubs[i].id + '" class="UTub draw"><input type="radio" id="UTub-' + UTubs[i].id + '" name="UTubSelection" value="' + UTubs[i].name + '"><b>' + UTubs[i].name + '</b></label>';
    }
    $('#UTubDeck').find('form')[0].innerHTML = radioHTML;
}

function findUTubID() {
    // Find which UTub was requested
    radioButton = $('input[type=radio]:checked')[0];
    $('#UTubHeader')[0].innerHTML = radioButton.value;  // Update center panel header
    str = radioButton.id;
    return str.split('-')[1];
}

function getUtubInfo(selectedUTubID) {
    // Just to make sure hidden, if coming from "/create_utub"
    $('#TubImage').hide();

    // Pull data from db
    return $.getJSON('/home?UTubID=' + selectedUTubID, function (UTubJSON) { buildUTub(UTubJSON) });
}

function buildUTub(selectedUTub) {
    //Use local variables, pass them in to the subsequent functions as required
    var selectedUTubID = selectedUTub.id;
    var dictURLs = selectedUTub.urls;
    var dictTags = selectedUTub.tags;
    var dictUsers = selectedUTub.members;
    var creator = selectedUTub.created_by;
    let currentUserID = $('.user').attr('id');

    // Clear 
    resetUTubs();

    // Update modal-targets
    $('#addURL').attr('modal-target', "/add_url/" + selectedUTubID);
    $('#addUser').attr('modal-target', "/add_user/" + selectedUTubID);
    // $('#deleteUTub').attr('modal-target', "/delete_utub/" + selectedUTubID + "/" + currentUserID);
    $('#deleteUTub').attr('modal-target', "/delete_utub/" + selectedUTubID);

    // Center panel
    buildURLDeck(dictURLs, dictTags);

    // LH panels
    buildTagDeck(dictTags);

    // RH panels
    // Update UTub description, not yet implemented on backend
    // $('#UTubInfo')[0].innerHTML = selectedUTub.description;

    gatherUsers(dictUsers, creator);
}

// Build center panel URL-tag list for selectedUTub
function buildURLDeck(dictURLs, dictTags) {
    $('#listURLs')[0].innerHTML = '';

    for (let i in dictURLs) {
        let col = document.createElement('div');
        let card = document.createElement('div');
        let deleteSpan = document.createElement('span');
        let deleteButton = document.createElement('i');
        // let cardImg = document.createElement('img');
        let cardBody = document.createElement('div');
        let cardTitle = document.createElement('h5');
        let cardText = document.createElement('p');

        $(col).attr({ 'class': 'col-md-12 col-lg-4 col-xl-3 mb-3' })

        $(card).attr({
            'urlid': dictURLs[i].url_id,
            'class': 'card url',
            'draggable': 'true',
            'ondrop': 'dropIt(event)',
            'ondragover': 'allowDrop(event)',
            'ondragstart': 'dragStart(event)'
        })

        $(deleteSpan).attr({
            'class': 'pull-right clickable close-icon',
            'data-effect': 'fadeOut',
            'style': 'display: none'
        })

        $(deleteButton).attr({
            'class': 'fa fa-times',
            'data-effect': 'fadeOut'
        })

        // $(cardImg).attr({
        //     'class': 'card-img-top',
        //     'src': '...',
        //     'alt': '"Card image cap'
        // })

        $(cardBody).attr({ 'class': 'card-body' })

        $(cardTitle).attr({ 'class': 'card-title' })
        cardTitle.innerHTML = dictURLs[i].url_string

        $(cardText).attr({ 'class': 'card-text' })

        // Assemble url list items
        $(col).append(card);
        // $(card).append(cardImg);
        $(card).append(deleteSpan);
        $(deleteSpan).append(deleteButton);
        $(card).append(cardBody);
        $(cardBody).append(cardTitle);
        $(cardBody).append(cardText);


        // Build tag html strings 
        let tagArray = dictURLs[i].url_tags;
        let tagString = '';
        for (let j in tagArray) { // Find applicable tags in dictionary to apply to URL card
            let tag = dictTags.find(function (e) {
                if (e.id === tagArray[j]) {
                    return e.tag_string
                }
            });

            let tagSpan = document.createElement('span');
            $(tagSpan).attr({
                'class': 'tag',
                'tagid': tag[j].id,
                'value': tag[j].tag_string
            })
            $(cardText).append(tagSpan)
        }


        $('#listURLs').append(col);
    }
}

function updateURLDeck() {
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

// Build LH panel tag list in selectedUTub
function buildTagDeck(dictTags) {

    let html = '<label for="selectAll"><input id="selectAll" type="checkbox" name="selectAll" checked="true"> Select All </label>';

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
            html += '<label for="' + tagText + '" tagid=' + tagID + '><input class="tagCheckbox" type="checkbox" name="' + tagText + '" checked="true"> ' + tagText + ' </label>';
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

function selectURL(selectedURLid) {
    // Need to implement URL description display in card when selected
    // Find notes for selected URL
    // $('#URLInfo')[0].innerHTML = selectedURL.notes;
    let selectedUTubID = findUTubID();

    // Update hrefs
    $('#addTags').attr("modal-target", "/add_tag/" + selectedUTubID + "/" + selectedURLid);
    $('#EditURL').attr("onclick", "editURL(" + selectedUTubID + "," + selectedURLid + ")");
    $('#DeleteURL').attr("modal-target", "/delete_url/" + selectedUTubID + "/" + selectedURLid);
}

function resetUTubs() {
    // Reset tag deck
    tags = [];

    // Empty URL description
    $('#URLInfo')[0].innerHTML = '';

    // Empty TagsDeck
    $('#listTags')[0].innerHTML = '';

    // Update hrefs
    $('#addTags').attr("modal-target", "#");
    $('#EditURL').attr("onclick", "#");
    $('#DeleteURL').attr("modal-target", "#");
}

function accessLink() {
    if (!selectedURL.url_string.startsWith('https://')) {
        window.open('https://' + selectedURL.url_string, "_blank");
    } else {
        window.open(selectedURL.url_string, "_blank");
    }
}

function editURL(selectedUTubID, selectedURLid) {
    var URLcard = "div.url.selected[urlid=" + selectedURLid + "]";   // Find URL HTML with selected ID
    var liHTML = $(URLcard).find('h5.card-title');                   // Store pre-edit values
    var URLString = liHTML[0].innerHTML;
    console.log(URLString)
    var tags = liHTML.slice(1);
    tags = tags.map(i => '<span' + i)
    var tagString = liHTML.slice(1).map(i => '<span' + i).join('');

    $(URLcard).html('');                               // Clear li
    $('<input></input>').attr({                      // Replace with temporary input
        'type': 'text',
        'id': 'edit_url',
        'urlid': selectedURLid,
        'size': '30',
        'value': URLString
    }).appendTo($(URLcard));
    $(URLcard).html($(URLcard).html() + tagString);
    $('#edit_url').focus();

    $(document).on("blur", '#edit_url', function () {
        console.log($('#edit_url'))
        var urlText = $(this).val();
        var selectedURLid = $(this).attr('urlid');
        let request = $.ajax({
            type: 'post',
            url: "/edit_url/" + selectedUTubID + "/" + selectedURLid
        });
        request.done(function (response, textStatus, xhr) {
            if (xhr.status == 200) {
            }
        })
    });
}

function openModal(route) {
    console.log(route)
    $.get(route, function (formHtml) {
        $('#Modal .modal-content').html(formHtml);
        $('#Modal').modal('show');
        $('#submit').click(function (event) {
            event.preventDefault();
            // $('.modal-flasher').prop({'hidden': true});
            let request = $.ajax({
                url: route,
                type: "POST",
                data: $('#ModalForm').serialize(),
            });

            request.done(function (response, textStatus, xhr) {
                if (xhr.status == 200) {
                    $('#Modal').modal('hide');
                    // const flashElem = flashMessageBanner(response.message, response.category);
                    // flashElem.insertBefore($('.main-content'));

                    let rootRoute = route.split('/')[1];

                    switch (rootRoute) {
                        default:
                            console.log('Unimplemented route')
                        case 'create_utub':
                            createUTub(response.UtubID, response.UtubName);
                            break;
                        case 'delete_utub':
                            deleteUTub(route.split('/')[2])
                            break;
                        case 'add_url':
                            getUtubInfo(route.split('/')[2])
                            $('#urlNote').hide();
                            break;
                        case 'add_tag':
                            getUtubInfo(route.split('/')[2])
                            $('#urlNote').hide();
                            break;
                    }
                };
            });

            request.fail(function (xhr, textStatus, error) {
                if (xhr.status == 409) {
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
                console.log("Error: " + error);
            })
        });
    })
}

function createUTub(id, name) {
    radioHTML = '<label for="UTub-' + id + '" class="UTub draw active"><input type="radio" id="UTub-' + id + '" name="UTubSelection" value="' + name + '"><b>' + name + '</b></label>';
    $('#UTubDeck').find('form')[0].innerHTML += radioHTML;
    $('input[type=radio]').prop('checked', false);
    $('.UTub').removeClass('active');
    $('#UTub-' + id).prop('checked', true);
    $('#UTub-' + id).closest('.UTub').addClass('active');

    $('#UTubHeader')[0].innerHTML = "";
    $("<p id='urlNote'>Add a URL</p>").insertAfter("#UTubHeader");

    getUtubInfo(findUTubID())
}

function deleteUTub(id) {
    // Update UTub Deck
    $('#UTub-' + id).parent().remove();

    // Clear URL Deck
    $('#listURLs')[0].innerHTML = "";

    // Update UTub center panel
    $('#TubImage').show();
    $('#UTubHeader')[0].innerHTML = "Select a UTub";
}