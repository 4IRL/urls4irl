// Tag UI Interactions

$(document).ready(function () {

    // Selected Tag
    $('#TagDeck').on('click', function (e) {
        // Refactor into separate function at some point
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
        filterURLDeck();
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
});

// Tag Functions

// Build LH panel tag list in selectedUTub
function buildTagDeck(dictTags) {
    if (dictTags.length == 0) {
        // User has no Tags in this UTub
        $('#TagDeck').find('h2')[0].innerHTML = "Create a Tag";
        $('#listTags')[0].innerHTML = '<h5>No tags applied to any URLs in this UTub</h5>'; // I still want this to show if user creates a new tag but has not yet applied them to any URLs
    } else {
        // Instantiate UTubDeck (top left panel) with UTubs accessible to current user
        $('#TagDeck').find('h2')[0].innerHTML = "Tags";

        const parent = $('#listTags')

        // Start with the select all checkbox
        let container = document.createElement('div');
        let label = document.createElement('label');
        let selAllCheck = document.createElement('input');


        $(container).attr({ 'class': 'checkbox-container' })

        $(label).attr({ 'for': 'selectAll' })

        $(selAllCheck).attr({
            'type': 'checkbox',
            'id': 'selectAll',
            'name': 'selectAll',
            'checked': 'true'
        })

        $(label).append(selAllCheck);
        label.innerHTML += 'Select All';
        $(container).append(label);
        parent.append(container);

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

        // Loop through all tags and provide checkbox input for filtering
        for (let i in dictTags) {
            let tagText = dictTags[i].tag_string;
            let tagID = dictTags[i].id;
            let container = document.createElement('div');
            let label = document.createElement('label');
            let checkbox = document.createElement('input');

            $(container).attr({ 'class': 'checkbox-container' })

            $(label).attr({ 'for': 'Tag-' + tagID })

            $(checkbox).attr({
                'type': 'checkbox',
                'id': 'Tag-' + tagID,
                'tagid': tagID,
                'name': 'Tag' + i,
                'checked': 'checked'
            })

            $(label).append(checkbox);
            label.innerHTML += tagText;
            $(container).append(label);
            parent.append(container);
        }

        // New Tag input text field. Initially hidden, shown when create Tag is requested. Input field recreated here to ensure at the end of list after creation of new Tag
        let wrapper = document.createElement('div');
        let input = document.createElement('input');
        let submit = document.createElement('i');

        $(wrapper).attr({
            'id': 'createTag',
            'style': 'display: none'
        })

        $(input).attr({
            'type': 'text',
            'class': 'userInput',
            'placeholder': 'New Tag name',
            'size': '30',
            'onblur': 'hideInput(event)'
        })

        $(submit).attr({ 'class': 'fa fa-check-square fa-2x text-success mx-1' })

        wrapper.append(input);
        wrapper.append(submit);
        parent.append(wrapper);
    }
}

// Add a tag to the selected URL
function addTag(selectedUTubID, selectedURLid) {
    var jQuerySel = "div.url.selected[urlid=" + selectedURLid + "]";    // Find jQuery selector with selected ID          
    var cardTagDeck = $(jQuerySel).find('div.URLTags');                 // Find appropriate card element

    if ($('#new_tag').length) $('#new_tag').focus()
    else {
        $('<input></input>').attr({     // Replace with temporary input
            'type': 'text',
            'id': 'new_tag',
            'size': '30'
        }).appendTo($(cardTagDeck));
        $('#new_tag').focus()
    }

    $('#new_tag').on('blur keyup', function (e) {
        var keycode = (e.keyCode ? e.keyCode : e.which);
        if (e.type === 'blur' || keycode == '13') {
            var tagText = $(this).val();                    // Need to send this back to the db somehow
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

// Clear the Tag Deck
function resetTagDeck() {
    $('#listTags').empty();
}