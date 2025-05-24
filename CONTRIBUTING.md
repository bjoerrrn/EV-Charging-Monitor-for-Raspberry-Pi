# Contributing to EV Charging Monitor for Raspberry Pi

We welcome contributions to the Wallbox Monitor project! Whether it's bug fixes, new features, improvements to documentation, or support for new wallbox models, your help is appreciated.

Please take a moment to review this document to understand how you can best contribute.

---

## 💡 How to Contribute

There are several ways you can contribute to this project:

1.  **Report Bugs:** If you find a bug, please check the [issues page](https://github.com/bjoerrrn/shellrecharge-wallbox-monitor/issues) to see if it's already reported. If not, open a new issue using the "Bug Report" template.
2.  **Suggest Features:** Have an idea for a new feature or an improvement? Open a new issue using the "Feature Request" template.
3.  **Improve Documentation:** Spot a typo, unclear explanation, or missing information in the `README.md` or other documentation? Feel free to submit a pull request with your changes.
4.  **Submit Code Changes (Pull Requests):** If you've developed a fix or a new feature, we'd love to see it! Please follow the guidelines below for submitting pull requests.
5.  **Support New Wallbox Models:** This is a key area where we need your help! If you have a different wallbox model and would like to see it supported, please read the section below.

---

## 🐞 Reporting Bugs

When reporting a bug, please use the provided [Bug Report template](.github/ISSUE_TEMPLATE/bug_report.md) and include as much detail as possible:

* **Steps to reproduce:** Clear, numbered steps that describe how to trigger the bug.
* **Expected behavior:** What you expected to happen.
* **Actual behavior:** What actually happened.
* **Environment details:** Wallbox model, Raspberry Pi model, OS, Python version, and script version.
* **Screenshots/Logs:** Any relevant screenshots or log output that can help diagnose the issue.

---

## ✨ Suggesting Features

When suggesting a new feature or enhancement, please use the provided [Feature Request template](.github/ISSUE_TEMPLATE/feature_request.md). Describe:

* The problem the feature solves.
* The proposed solution.
* Any alternative solutions you've considered.

---

## 👨‍💻 Submitting Code Changes (Pull Requests)

Before submitting a pull request, please ensure you've:

1.  **Forked** the repository and created a new branch for your feature or bug fix.
    ```bash
    git checkout -b feature/your-feature-name main
    # or
    git checkout -b bugfix/your-bug-fix-name main
    ```
2.  **Written clean, readable code** that adheres to the existing code style.
3.  **Tested your changes thoroughly.**
4.  **Updated any relevant documentation** (e.g., `README.md`) if your changes introduce new features or modify existing behavior.
5.  **Written a clear, concise commit message** that summarizes your changes.
6.  **Ensured your branch is up-to-date** with the `main` branch of the upstream repository.

Once you're ready, submit your pull request and link it to any relevant issues.

---

## 🔌 Adding Support for New Wallbox Models

Extending this script to support new wallbox models is a primary goal, but it requires specific information about the wallbox's web interface or API.

**How you can help:**

If you own a wallbox model not currently supported, and you're willing to assist, we'd appreciate your help in gathering the necessary data. This often involves:

1.  **Providing secure remote access to your local network/Wallbox interface:**
    To properly integrate a new wallbox, we often need temporary, secure remote access to the wallbox's local web interface or API. This allows us to inspect the web interface, analyze network traffic, and identify the data points needed for monitoring.
    * **What we need:** Typically, this means access to your local network (e.g., via VPN) or a securely exposed (e.g., port-forwarded) web interface/API endpoint of your wallbox. This allows us to run the Selenium-based analysis or directly interact with the wallbox's local API.
    * **Our commitment:** We will only use this access to analyze the wallbox's communication and integrate its data into the script. We will not access or store any personal data. Access will be temporary and you can revoke it at any time once the integration is complete.
    * **Contact:** Please reach out to me directly via [Discord](https://discordapp.com/users/371404709262786561) to discuss the details and arrange secure access. We can discuss options like an NDA if you have privacy concerns, although for an open-source project, this is less common.

2.  **Providing technical details (if remote access isn't possible):**
    If secure remote access is not feasible for you, you might be able to provide information manually:
    * **Screenshots of your wallbox's local web interface:** Especially the charging status, current power, and consumed energy.
    * **Browser developer console output:** Network requests (XHR/Fetch) and their responses while charging is active.
    * **Any publicly available API documentation** for your specific wallbox model.

Your collaboration is crucial for making this project compatible with a wider range of wallboxes!

---

## ❓ Questions?

If you have any questions about contributing, don't hesitate to open an issue or reach out directly on [Discord](https://discordapp.com/users/371404709262786561).

Thank you for your interest in contributing to Wallbox Monitor!
