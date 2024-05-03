const target = arguments[0];
const offsetX = arguments[1];
const offsetY = arguments[2];

const document = target.ownerDocument || document;
const window = document.defaultView || window;

const input = document.createElement('INPUT');
input.type = 'file';
input.onchange = function () {
    const rect = target.getBoundingClientRect();
    const x = rect.left + (offsetX || (rect.width >> 1));
    const y = rect.top + (offsetY || (rect.height >> 1));

    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(input.files[0]);

    console.log('Got uploads: ' + dataTransfer.items);

    for (let t = 0; t < dataTransfer.items.length; t++) {
        const n = dataTransfer.items[t];
        console.log("Upload " + t + ": " + n.kind);
        if (n.kind === "file") {
            const e = n.getAsFile();
            if (e) {
                console.log("File upload " + t + ": " + e.name);
            } else {
                console.warn("Cannot get file");
            }
        } else {
            console.warn("Not a file upload");
        }
    }

    ['dragenter', 'drop', 'dragleave'].forEach(function (name) {
        console.log('Dispatching mouse event with file transfer')
        const evt = document.createEvent('MouseEvent');
        evt.initMouseEvent(name, !0, !0, window, 0, 0, 0, x, y, !1, !1, !1, !1, 0, null);
        evt.dataTransfer = dataTransfer;
        target.dispatchEvent(evt);
    });

    // setTimeout(function () {
    //     document.body.removeChild(input);
    // }, 25);
};
target.appendChild(input);

console.log('Created file upload input')

// noinspection JSAnnotator
return input;
