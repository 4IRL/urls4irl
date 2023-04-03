// Tag UI Interactions

$(document).ready(function () {

    // Selected Tag
    $('#TagDeck').on('click', function (e) {
        // Refactor into separate function at some point
        let div;
        let label;
        let input;
        let clickedTagID;

        // Handle extra click behvaiors (div and label should also toggle input[type='checkbox'])
        // if ($(e.target)[0].className.toLowerCase() == 'tag-input-container') {
        //     div = $(e.target);
        //     input = $(div.find('input')[0]);
        //     input.prop("checked", input.prop("checked"));
        // } else if (e.target.nodeName.toLowerCase() == 'label') {
        //     console.log("label clicked")
        //     // Label clicked. Reset input var. Also toggles checkbox and assigns clickedTagID
        //     label = $(e.target);
        //     input = label.children();
        //     input.prop("checked", input.prop("checked"));
        //     e.preventDefault();
        // } else {
        //     console.log("input clicked")
        //     // Input clicked. Already toggles checkbox
        //     input = $(e.target);
        //     // input.prop("checked", !input.prop("checked"));
        //     label = input.parent();
        // }

        // if (input[0].id == 'selectAll') {       // Select all behavior
        //     if (e.target.nodeName.toLowerCase() == 'label') {
        //         e.preventDefault();
        //     }

        //     // Toggle all filter tags
        //     $('input[type=checkbox]').prop("checked", input[0].checked);

        //     // Hide/Show all tag spans
        //     spanObjs = $('span.tag')
        //     if (input[0].checked) {
        //         $($(spanObjs)).show()
        //     } else {
        //         $($(spanObjs)).hide()
        //     }
        // } else {                                // Other tag filter selection behavior
        //     let selectAllBool = true;
        //     $('input[type=checkbox]').each(function (i) {
        //         if (i !== 0) {
        //             selectAllBool &= $(this).prop("checked");
        //         }
        //     })

        //     $('#selectAll').prop("checked", selectAllBool);

        //     clickedTagID = parseInt(label.attr("tagid"));

        //     // Hide/Show corresponding tag span
        //     spanObjs = $('span[tagid="' + clickedTagID + '"]')
        //     $($(spanObjs)).toggle()
        // }
    });

    // Listen for click on toggle checkbox
    // $('#selectAll').click(function (event) {
    //     if (this.checked) {
    //         // Iterate each checkbox
    //         $(':checkbox').each(function () {
    //             this.checked = true;
    //         });
    //     } else {
    //         $(':checkbox').each(function () {
    //             this.checked = false;
    //         });
    //     }
    // });
});

// Tag Functions

// Build LH panel tag list in selectedUTub
function buildTagDeck(dictTags) {
    const parent = $('#listTags');
    // const gparent = parent.parent();
    // console.log(gparent)

    if (dictTags.length == 0) {
        // User has no Tags in this UTub
        $('#TagDeck').find('h2')[0].innerHTML = "Create a Tag";
        $('#editTagButton').hide();
        parent[0].innerHTML = '<h5>No tags applied to any URLs in this UTub</h5>'; // I still want this to show if user creates a new tag but has not yet applied them to any URLs
    } else {
        // Instantiate TagDeck (bottom left panel) with tags in current UTub
        $('#TagDeck').find('h2')[0].innerHTML = "Tags";
        $('#editTagButton').show();

        // 1. Select all checkbox
        let container = document.createElement('div');
        let label = document.createElement('label');
        let selAllCheck = document.createElement('input');

        $(container).attr({
            'id': 'selectAll',
            'class': 'selected',
            'onclick': "filterTags('all'); filterURLDeck()"
        })

        $(selAllCheck).attr({
            'type': 'checkbox',
            'id': 'selectAll',
            'name': 'selectAll',
            'checked': 'true',
            // 'onclick': "filterTags('all'); filterURLDeck()"
        })

        $(label).attr({
            'for': 'selectAll',
            // 'onclick': "filterTags('all'); filterURLDeck()"
        })

        label.innerHTML = 'Select All';
        // $(container).append(selAllCheck);
        $(container).append(label);
        parent.append(container);
        // gparent.insertBefore(container, parent);

        // 2a. Alpha sort tags based on tag_string
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

        // 2b. Loop through all tags and provide checkbox input for filtering
        for (let i in dictTags) {
            let tagText = dictTags[i].tag_string;
            let tagID = dictTags[i].id;
            let container = document.createElement('div');
            let label = document.createElement('label');
            let checkbox = document.createElement('input');

            $(container).attr({
                'tagid': tagID,                
                'class': 'tag-input-container selected',
                'onclick': "filterTags(" + tagID + "); filterURLDeck()"
            })

            $(label).attr({ 'for': 'Tag-' + tagID })

            $(checkbox).attr({
                'type': 'checkbox',
                'id': 'Tag-' + tagID,
                'tagid': tagID,
                'name': 'Tag' + i,
                'checked': 'checked'
            })

            label.innerHTML += tagText;
            // $(container).append(checkbox);
            $(container).append(label);
            parent.append(container);
        }

    }
    // New Tag input text field. Initially hidden, shown when create Tag is requested. Input field recreated here to ensure at the end of list after creation of new Tag
    let wrapper = document.createElement('div');
    let input = document.createElement('input');
    let submit = document.createElement('i');

    $(wrapper).attr({
        'style': 'display: none'
    })

    $(input).attr({
        'type': 'text',
        'id': 'createTag',
        'class': 'userInput',
        'placeholder': 'New Tag name',
        'onblur': 'postData(event, "createTag")'
    })

    $(submit).attr({ 'class': 'fa fa-check-square fa-2x text-success mx-1' })

    wrapper.append(input);
    wrapper.append(submit);
    parent.append(wrapper);
}

// Handle all display changes related to creating a new UTub
function createTag(id, name) {

    let div = document.createElement('div');
    let label = document.createElement('label');
    let checkbox = document.createElement('input');


    $(div).attr({ 'class': 'checkbox-container' })

    $(label).attr({
        'for': 'UTub-' + id,
        'class': 'UTub draw active',
        'onclick': "changeUTub(" + id + ")"
    })
    label.innerHTML = '<b>' + name + '</b>';

    $(checkbox).attr({
        'type': 'radio',
        // 'name': 'UTub' + i, need to extract the length of current UTubs list, increment and document here
        'id': 'UTub-' + id,
        'utubid': id,
        'value': name
    })

    $(label).append(checkbox);
    $(div).append(label);

    // Move "createUTub" element to the end of list
    let UTubList = $('#listUTubs').children();
    const createUTubEl = $(UTubList[UTubList.length - 1]).detach();
    $('#listUTubs').append(label);
    $('#listUTubs').append(createUTubEl);

    $('#UTubDeck').find('h2')[0].innerHTML = "Create a UTub";
    $('#UTub-' + id).prop('checked', true);

    $('#addURL').show();
    $('#UTubHeader')[0].innerHTML = name;
    $('#UPRRow')[0].innerHTML = "Add a URL";
}

// Allows user to edit all tags in the UTub 
function editTags(handle) {

    $('#editTagButton').toggle();
    $('#submitTagButton').toggle();
    var listTagDivs = $('#listTags').children();

    for (let i in listTagDivs) {
        if (i == 0 || i >= listTagDivs.length - 1) { } else {
            if (handle == 'submit') { // Editing, then handle submission
                console.log('submit initiated')
                var tagID = $(listTagDivs[i]).find('input[type="checkbox"]')[0].tagid;
                var tagText = $($(listTagDivs[i]).find('input[type="text"]')).val();
                console.log(tagID)
                console.log(tagText)
                postData([tagID, tagText], 'editTags')
            } else { // User wants to edit, handle input text field display
                var tagText = $(listTagDivs[i]).find('label')[0].innerHTML;

                var input = document.createElement('input');
                $(input).attr({
                    'type': 'text',
                    'class': 'userInput',
                    'placeholder': 'Edit tag name',
                    'value': tagText
                })
                $(listTagDivs[i]).find('label').hide();
                $(listTagDivs[i]).append(input);
            }
        }
    }
}

// Add a tag to the selected URL
function addTag(selectedUTubID, selectedURLid) {
    var jQuerySel = "div.url.selected[urlid=" + selectedURLid + "]";    // Find jQuery selector with selected ID          
    var cardTagDeck = $(jQuerySel).find('div.URLTags');                 // Find appropriate card element

    if ($('#new_tag').length) $('#new_tag').focus()
    else {
        $('<input></input>').attr({                                     // Replace with temporary input
            'type': 'text',
            'id': 'new_tag',
            'size': '30'
        }).appendTo($(cardTagDeck));
        $('#new_tag').focus()
    }

    $('#new_tag').on('blur keyup', function (e) {
        var keycode = (e.keyCode ? e.keyCode : e.which);
        if (e.type === 'blur' || keycode == '13') {
            var tagText = $(this).val();                                // Need to send this back to the db somehow
            let request = $.ajax({
                type: 'post',
                url: "/tag/add/" + selectedUTubID + "/" + selectedURLid,
                data: tagText
            });

            request.done(function (response, textStatus, xhr) {
                if (xhr.status == 200) {
                    cardTagDeck[0].innerHTML = updatedURLText;
                } else {
                    URLStringField[0].innerHTML = updatedURLText;
                }
            })
        }
    })
}

// Remove tag from selected URL
function removeTag(tagID) {
    var UTubID = currentUTubID();
    var URLID = selectedURLID();

    let request = $.ajax({
        type: 'post',
        url: '/tag/remove/' + UTubID + '/' + URLID + '/' + tagID
    });

    request.done(function (response, textStatus, xhr) {
        if (xhr.status == 200) {
            console.log($('div.url[urlid=' + URLID + ']'))
            console.log($('div.url[urlid=' + URLID + ']').find('span.tag[' + tagID + ']'))
            $('div.url[urlid=' + URLID + ']').find('span.tag[tagid=' + tagID + ']').remove();
        }
    })

    request.fail(function (xhr, textStatus, error) {
        if (xhr.status == 409) {
            console.log("Failure. Status code: " + xhr.status + ". Status: " + textStatus);
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
}

// Update tag display to reflect changes in response to a "Select All" filter request
function filterTags(tagID) {

    $('div[tagid=' + tagID + ']').toggleClass('selected')

    let input = $('#selectAll');
    let tagList = $('.tag-input-container');
    console.log("filter tags")
    if (tagID == 'all') {

        console.log("filter all tags")
        console.log(input.hasClass('selected'))

        // Toggle all filter tags to match "Select All" checked status
        input.toggleClass('selected')
        input.hasClass('selected') ? tagList.addClass('selected') : tagList.removeClass('selected')

        let spanObjs = $('span.tag');
        if (input.hasClass('selected')) {
            spanObjs.show()
        } else {
            spanObjs.hide()
        }
    } else {
        $('#selectAll').removeClass('selected')
        $('span[tagid=' + tagID + ']').toggle();
    }
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

// Clear the Tag Deck
function resetTagDeck() {
    $('#listTags').empty();
}