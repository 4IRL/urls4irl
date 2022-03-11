$('input[type=radio]').on('click', function () {
    console.log($('#UTubHeader'))
    $('#UTubHeader')[0].innerHTML = $('input[type=radio]:checked')[0].value;
})