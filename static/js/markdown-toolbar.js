/* Formatting toolbar for the Markdown body textareas on the blog and
 * portfolio add/edit forms. Wraps the current selection (or the current
 * line, for block-level buttons) with the right Markdown syntax, and the
 * Image button uploads a file straight to /admin/upload-image and inserts
 * the resulting ![](url) at the cursor -- no separate tab needed.
 *
 * Vanilla JS, no build step, no framework: matches how the rest of this
 * site is built (see AGENTS.md).
 */
document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll(".md-toolbar").forEach(function (toolbar) {
    var textarea = document.getElementById(toolbar.dataset.target);
    if (!textarea) {
      return;
    }

    function wrapSelection(before, after) {
      if (after === undefined) {
        after = before;
      }
      var start = textarea.selectionStart;
      var end = textarea.selectionEnd;
      var selected = textarea.value.slice(start, end);
      textarea.setRangeText(before + selected + after, start, end, "end");
      // setRangeText's "select" mode selects the whole replacement,
      // markers included -- typing then would overwrite the ** along with
      // the word. Re-select just the original text (or, if nothing was
      // selected, collapse the cursor to sit between the markers) instead.
      textarea.setSelectionRange(start + before.length, start + before.length + selected.length);
      textarea.focus();
    }

    function prefixCurrentLine(prefix) {
      var start = textarea.selectionStart;
      var lineStart = textarea.value.lastIndexOf("\n", start - 1) + 1;
      textarea.setRangeText(prefix, lineStart, lineStart, "end");
      textarea.focus();
    }

    function insertAtCursor(text) {
      var start = textarea.selectionStart;
      var end = textarea.selectionEnd;
      textarea.setRangeText(text, start, end, "end");
      textarea.focus();
    }

    var imageInput = toolbar.querySelector(".md-image-input");
    var imageButton = toolbar.querySelector('button[data-md="image"]');
    var imageButtonLabel = imageButton ? imageButton.textContent : "";

    toolbar.querySelectorAll("button[data-md]").forEach(function (button) {
      button.addEventListener("click", function () {
        switch (button.dataset.md) {
          case "bold":
            wrapSelection("**");
            break;
          case "italic":
            wrapSelection("*");
            break;
          case "code":
            wrapSelection("`");
            break;
          case "link":
            var url = window.prompt("Link URL:", "https://");
            if (url) {
              wrapSelection("[", "](" + url + ")");
            }
            break;
          case "heading":
            prefixCurrentLine("## ");
            break;
          case "list":
            prefixCurrentLine("- ");
            break;
          case "quote":
            prefixCurrentLine("> ");
            break;
          case "image":
            if (imageInput) {
              imageInput.click();
            }
            break;
        }
      });
    });

    if (imageInput) {
      imageInput.addEventListener("change", function () {
        var file = imageInput.files[0];
        if (!file) {
          return;
        }

        imageButton.disabled = true;
        imageButton.textContent = "Uploading...";

        var formData = new FormData();
        formData.append("image", file);

        fetch("/admin/upload-image", {
          method: "POST",
          headers: { Accept: "application/json" },
          body: formData,
        })
          .then(function (response) {
            return response.json().then(function (data) {
              return { ok: response.ok, data: data };
            });
          })
          .then(function (result) {
            if (result.ok) {
              insertAtCursor("![](" + result.data.url + ")");
            } else {
              window.alert(result.data.error || "Upload failed.");
            }
          })
          .catch(function () {
            window.alert("Upload failed. Check your connection and try again.");
          })
          .finally(function () {
            imageButton.disabled = false;
            imageButton.textContent = imageButtonLabel;
            imageInput.value = "";
          });
      });
    }
  });
});
