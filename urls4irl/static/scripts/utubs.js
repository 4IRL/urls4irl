// UTub UI Interactions

$(document).ready(function () {

    // Instantiate UTubDeck with user's accessible UTubs
    buildUTubDeck(UTubsList);

});

// UTub Related Functions

function findUTubID() {
    // Find which UTub was requested
    var currentUTub = $('.UTub.active');

    var radioButton = currentUTub.find('input')[0];
    return radioButton.attr('utubid');
}

// Simple function to streamline the jQuery selector extraction of UTub ID. And makes it easier in case the ID is encoded in a new location in the future
function currentUTubID() {
    return $('.UTub.active').find('input').attr('utubid');
}

// Simple function to streamline the AJAX call to db for updated info
function getUtubInfo(selectedUTubID) {
    return $.getJSON('/home?UTubID=' + selectedUTubID)
}

function buildUTubDeck(UTubs) {
    const parent = $('#listUTubs')

    if (UTubs.length == 0) {
        // User has no UTubs
        $('#UTubHeader')[0].innerHTML = "<----------- Oops, no UTubs! Create one!";
        $('#UTubDeck').find('h2')[0].innerHTML = "Create a UTub";
    } else {
        // Instantiate UTubDeck (top left panel) with UTubs accessible to current user
        $('#UTubDeck').find('h2')[0].innerHTML = "UTubs";

        for (i in UTubs) {
            let label = document.createElement('label');
            let radio = document.createElement('input');

            $(label).attr({
                'for': 'UTub-' + UTubs[i].id,
                'class': 'UTub draw',
                'onclick': "changeUTub(" + UTubs[i].id + ")"
            })
            label.innerHTML = '<b>' + UTubs[i].name + '</b>';

            $(radio).attr({
                'type': 'radio',
                'name': 'UTub' + i,
                'id': 'UTub-' + UTubs[i].id,
                'utubid': UTubs[i].id,
                'value': UTubs[i].name
            })

            $(label).append(radio);
            parent.append(label);
        }
    }

    // New UTub input text field. Initially hidden, shown when create UTub is requested. Input field recreated here to ensure at the end of list after creation of new UTubs
    let wrapper = document.createElement('div');
    let input = document.createElement('input');
    let submit = document.createElement('i');

    $(wrapper).attr({
        'style': 'display: none'
    })

    $(input).attr({
        'type': 'text',
        'id': 'createUTub',
        'class': 'userInput',
        'placeholder': 'New UTub name',
        'onblur': 'postData(event, "createUTub")'
    })

    $(submit).attr({ 'class': 'fa fa-check-square fa-2x text-success mx-1' })

    wrapper.append(input);
    wrapper.append(submit);
    parent.append(wrapper);
}

// User selected a UTub, display data
function changeUTub(selectedUTubID) {
    // Unselect any already selected UTub
    $('#listUTubs').find('.active').removeClass('active');

    // UTub deck display updates
    var selectedUTubRadio = $('input[utubid=' + selectedUTubID + ']');
    selectedUTubRadio.parent().toggleClass('active');
    var UTubName = selectedUTubRadio[0].value;
    $('#deleteUTubButton').show();

    // Tag deck display updates
    $('#createTagButton').show();

    // URL deck display updates
    $('#UTubHeader')[0].innerHTML = UTubName;
    $('#editUTub')[0].value = UTubName;

    getUtubInfo(selectedUTubID).then(function (selectedUTub) {
        //Use local variables, pass them in to the subsequent functions as required
        var dictURLs = selectedUTub.urls;
        var dictTags = selectedUTub.tags;
        var dictUsers = selectedUTub.members;
        var creator = selectedUTub.created_by;
        let currentUserID = $('.user').attr('id');

        resetTagDeck();
        resetURLDeck();

        // LH panel
        buildTagDeck(dictTags);

        // Center panel
        buildURLDeck(dictURLs, dictTags);

        // RH panels
        // Update UTub description, not yet implemented on backend
        // $('#UTubInfo')[0].innerHTML = selectedUTub.description;

        gatherUsers(dictUsers, creator);
    })
}

// Handle all display changes related to creating a new UTub
function createUTub(id, name) {

    let label = document.createElement('label');
    let radio = document.createElement('input');

    $(label).attr({
        'for': 'UTub-' + id,
        'class': 'UTub draw active',
        'onclick': "changeUTub(" + id + ")"
    })
    label.innerHTML = '<b>' + name + '</b>';

    $(radio).attr({
        'type': 'radio',
        // 'name': 'UTub' + i, need to extract the length of current UTubs list, increment and document here
        'id': 'UTub-' + id,
        'utubid': id,
        'value': name
    })

    $(label).append(radio);

    // Move "createUTub" element to the end of list
    let UTubList = $('#listUTubs').children();
    const createUTubEl = $(UTubList[UTubList.length - 1]).detach();
    $('#listUTubs').append(label);
    $('#listUTubs').append(createUTubEl);

    $('#UTubDeck').find('h2')[0].innerHTML = "UTubs";
    $('#UTub-' + id).prop('checked', true);

    $('#addURL').show();
    $('#UTubHeader')[0].innerHTML = name;
    $('#UPRRow')[0].innerHTML = "Add a URL";

    changeUTub(id)
}

// Edit UTub name and description. Should also automatically run after creation of a new UTub to offer the option of including a UTub description.
function editUTub() {
    showInput('editUTub')
    console.log("showinput complete")
    showInput('editUTubDescription')
}

function deleteUTub() {
    var id = currentUTubID();

    let request = $.ajax({
        type: 'post',
        url: "/utub/delete/" + id
    });

    request.done(function (response, textStatus, xhr) {
        if (xhr.status == 200) {
            // Clear URL Deck
            resetURLDeck();
            resetTagDeck();

            // Update UTub Deck
            $('#UTub-' + id).parent().remove();

            // Update UTub center panel
            $('#UTubHeader')[0].innerHTML = "Select a UTub";
            $('#TagDeck').find('h2')[0].innerHTML = "No UTub Selected";
            if ($('#listUTubs').children().length <= 1) {
                $('#UTubHeader')[0].innerHTML = "<----------- Oops, no UTubs! Create one!";
                $('#UTubDeck').find('h2')[0].innerHTML = "Create a UTub";
            }
            $('#editUTub').hide();
            $('#addURL').hide();
            $('#UTubDescription').hide();
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
}

function confirmModal(handle) {

    // Modal adjustments
    switch (handle) {
        case 'deleteUTub':
            var modalTitle = 'Are you sure you want to delete this UTub?'
            break;
        case 'deleteUser':
            var modalTitle = 'Are you sure you want to remove this user from the current UTub?'
            break;
        default:
            console.log('Unimplemented')
    }

    $('.modal-title')[0].innerHTML = modalTitle

    $('#confirmModal').modal('show');

    $('#submit').click(function (e) {
        e.preventDefault();
        switch (handle) {
            case 'deleteUTub':
                deleteUTub()
                break;
            case 'deleteUser':
                removeUser()
                break;
            default:
                console.log('Unimplemented')
        }
    })
}