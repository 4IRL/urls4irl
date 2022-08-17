function allowDrop(ev) {
  ev.preventDefault();  // default is not to allow drop
}
function dragStart(ev) {
  // Store id for transfer
  ev.dataTransfer.setData("text/plain", ev.target.id);
}
function dropIt(ev) {
  // Origin data
  console.log(ev)
  let cardID = ev.dataTransfer.getData("text/plain");
  let cardEl = document.getElementById(cardID);
  let originEl = cardEl.parentElement;
  // Destination data
  let destEl = ev.target;
  let swapCardEl;
  if (destEl.className === "list-title" || destEl.className === "tag") {
    if (destEl.className === "tag") {
      swapCardEl = destEl;
    }
    destEl = destEl.parentElement;
  }

  // Compare List names to see if we are going between lists
  // or within the same list
  if (destEl.id !== originEl.id) {
    // Append to the list
    destEl.appendChild(cardEl);

  } else {
    // Same list. Swap two cards
    if (!(swapCardEl === undefined)) destEl.insertBefore(cardEl, swapCardEl)
  }
}

$(".add-group").on('click', async function () {
  // user input title
  let input = document.createElement('input');
  setAttributes(input, { "id": 'group-name-input' });
  $("#boardlists")[0].insertBefore(input, $("#boardlists")[0].firstChild);
  let inputEl = $("#group-name-input")[0];
  await awaitEnter();

  var ids = $('#boardlists > .board-list').map(function () {
    return this.id || null;
  }).get();

  // new group
  let newTitle = inputEl.value === '' ? "New Group" : inputEl.value;
  inputEl.remove();
  let group = document.createElement('div');
  setAttributes(group, { "id": '-group', "class": "board-list", "ondrop": "dropIt(event)", "ondragover": "allowDrop(event)" });
  group.innerHTML = '<div class="list-title"><h2>' + newTitle + '</h2></div><button class="edit-group"><i class="large material-icons">edit</i></button><button class="remove-group"><i class="large material-icons">remove</i></button><div class="list-content"></div>'

  $("#boardlists")[0].insertBefore(group, $("#boardlists")[0].firstChild);
});

$(".edit-group").on('click', async function () {
  console.log($(this)[0].parentNode)
  let listDiv = $(this)[0].parentNode.firstChild;
  let oldTitle = listDiv.innerText.split("editremove")[0];
  let groupDiv = listDiv.parentNode;
  let input = document.createElement('input');
  setAttributes(input, { "id": 'group-name-input' });
  $("#boardlists")[0].insertBefore(input, groupDiv);
  listDiv.style.display = "none";
  await awaitEnter();

  listDiv.textContent = inputEl.value === '' ? oldTitle : inputEl.value;
  listDiv.style.display = "";
  var nodes = listDiv.childNodes;
  for (var i = 0; i < nodes.length; i++) {
    nodes[i].style.display = "";
  }
  inputEl.remove();
});

function setAttributes(el, attrs) {
  for (var key in attrs) {
    el.setAttribute(key, attrs[key]);
  }
}

function awaitEnter() {
  return new Promise((resolve) => {
    document.addEventListener('keydown', onKeyHandler);
    function onKeyHandler(e) {
      if (e.keyCode === 13) {
        document.removeEventListener('keydown', onKeyHandler);
        resolve();
      }
    }
  });
}