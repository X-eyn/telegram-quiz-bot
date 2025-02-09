document.addEventListener('DOMContentLoaded', function() {
    const addQuestionButton = document.getElementById('add-question-button');
    const questionsContainer = document.getElementById('questions-container');
    const publishQuizButton = document.getElementById('publish-quiz-button');
    const quizTitleInput = document.getElementById('quiz-title');
    const quizDescriptionInput = document.getElementById('quiz-description');
    const quizReviewSection = document.querySelector('.quiz-review');
    const questionCreatorSection = document.querySelector('.question-creator');
    const quizPreviewContainer = document.getElementById('quiz-preview-container');
    const editQuizButton = document.getElementById('edit-quiz-button');
    const previewQuizButton = document.getElementById('preview-quiz-button');


    let questionCount = 0; // To keep track of question IDs

    addQuestionButton.addEventListener('click', function() {
        questionCount++;
        const questionIndex = questionCount;

        const questionForm = document.createElement('div');
        questionForm.classList.add('question-form');
        questionForm.innerHTML = `
            <h3>Question ${questionIndex}</h3>
            <div class="form-group">
                <label for="question-text-${questionIndex}">Question Text:</label>
                <textarea id="question-text-${questionIndex}" placeholder="Enter question text" required></textarea>
            </div>
            <div class="options-group" id="options-group-${questionIndex}">
                <h4>Options</h4>
                <div class="option-input">
                    <label for="option-1-${questionIndex}">Option 1:</label>
                    <input type="text" id="option-1-${questionIndex}" placeholder="Enter option 1" required>
                    <input type="radio" name="correct-answer-${questionIndex}" value="1" class="correct-answer-radio" required>
                </div>
                <div class="option-input">
                    <label for="option-2-${questionIndex}">Option 2:</label>
                    <input type="text" id="option-2-${questionIndex}" placeholder="Enter option 2" required>
                    <input type="radio" name="correct-answer-${questionIndex}" value="2" class="correct-answer-radio" required>
                </div>
            </div>
            <button class="add-option-button" data-question-index="${questionIndex}">Add Option</button>
        `;
        questionsContainer.appendChild(questionForm);

        updatePublishButtonState();

        const addOptionButton = questionForm.querySelector('.add-option-button');
        addOptionButton.addEventListener('click', function() {
            const currentQuestionIndex = this.dataset.questionIndex;
            const optionsGroup = document.getElementById(`options-group-${currentQuestionIndex}`);
            const optionCount = optionsGroup.querySelectorAll('.option-input').length;

            if (optionCount < 10) {
                const optionIndex = optionCount + 1;
                const newOptionInput = document.createElement('div');
                newOptionInput.classList.add('option-input');
                newOptionInput.innerHTML = `
                    <label for="option-${optionIndex}-${currentQuestionIndex}">Option ${optionIndex}:</label>
                    <input type="text" id="option-${optionIndex}-${currentQuestionIndex}" placeholder="Enter option ${optionIndex}" required>
                    <input type="radio" name="correct-answer-${currentQuestionIndex}" value="${optionIndex}" class="correct-answer-radio" required>
                `;
                optionsGroup.appendChild(newOptionInput);
            } else {
                alert("Maximum 10 options allowed per question.");
            }
            updatePublishButtonState();
        });

        // Event listeners for validation within the new question form
        const questionTextArea = questionForm.querySelector('textarea[id^="question-text-"]');
        questionTextArea.addEventListener('input', updatePublishButtonState);
        const optionInputs = questionForm.querySelectorAll('.option-input input[type="text"]');
        optionInputs.forEach(input => input.addEventListener('input', updatePublishButtonState));
        const correctAnswerRadios = questionForm.querySelectorAll('input[type="radio"][name^="correct-answer-"]');
        correctAnswerRadios.forEach(radio => radio.addEventListener('change', updatePublishButtonState));
    });

    function updatePublishButtonState() {
        const isFormValid = validateForm();
        publishQuizButton.disabled = !isFormValid;
    }

    function validateForm() {
        const quizTitle = quizTitleInput.value.trim();
        if (!quizTitle) {
            return false;
        }

        const questionForms = questionsContainer.querySelectorAll('.question-form');
        if (questionForms.length === 0) {
            return false;
        }

        for (const questionForm of questionForms) {
            const questionText = questionForm.querySelector('textarea[id^="question-text-"]').value.trim();
            if (!questionText) {
                return false;
            }

            const optionInputs = questionForm.querySelectorAll('.option-input input[type="text"]');
            let optionCount = 0;
            for (const optionInput of optionInputs) {
                if (optionInput.value.trim()) {
                    optionCount++;
                }
            }
            if (optionCount < 2) {
                return false;
            }

            const correctAnswer = questionForm.querySelector('input[name^="correct-answer-"]:checked');
            if (!correctAnswer) {
                return false;
            }
        }

        return true;
    }

    function generateQuizPreview() {
        const quizData = collectQuizData();
        let previewHTML = '';

        previewHTML += `<h3>${quizData.title}</h3>`;
        if (quizData.description) {
            previewHTML += `<p>${quizData.description}</p>`;
        }

        quizData.questions.forEach((question, questionIndex) => {
            previewHTML += `<div class="preview-question">
                <h4>Question ${questionIndex + 1}: ${question.questionText}</h4>
                <ul class="preview-options">`;
            question.options.forEach((option, optionIndex) => {
                const isCorrect = (optionIndex + 1) === parseInt(question.correctAnswerIndex);
                const optionClass = isCorrect ? 'correct-answer' : '';
                previewHTML += `<li class="${optionClass}">${option.text}</li>`;
            });
            previewHTML += `</ul></div>`;
        });

        quizPreviewContainer.innerHTML = previewHTML;
    }

    function collectQuizData() {
        const quizTitle = quizTitleInput.value.trim();
        const quizDescription = quizDescriptionInput.value.trim();
        const questions = [];
        const questionForms = questionsContainer.querySelectorAll('.question-form');

        questionForms.forEach(questionForm => {
            const questionText = questionForm.querySelector('textarea[id^="question-text-"]').value.trim();
            const options = [];
            const optionInputs = questionForm.querySelectorAll('.option-input input[type="text"]');
            optionInputs.forEach(optionInput => {
                options.push({ text: optionInput.value.trim() });
            });
            const correctAnswerRadio = questionForm.querySelector('input[name^="correct-answer-"]:checked');
            const correctAnswerIndex = correctAnswerRadio ? correctAnswerRadio.value : null;

            questions.push({
                questionText: questionText,
                options: options,
                correctAnswerIndex: correctAnswerIndex
            });
        });

        return {
            title: quizTitle,
            description: quizDescription,
            questions: questions
        };
    }


    publishQuizButton.addEventListener('click', function() {
        if (validateForm()) {
            const quizData = collectQuizData();
            console.log("Quiz Data to be sent:", quizData);

            if (window.Telegram && window.Telegram.WebApp) {
                const webApp = window.Telegram.WebApp;
                webApp.sendData(JSON.stringify(quizData));
                webApp.close();
                alert("Quiz data sent to bot!");
            } else {
                alert("Telegram WebApp API not available. Are you running this in Telegram?");
                console.error("Telegram WebApp API not available.");
            }

            generateQuizPreview(); // You can adjust this part if needed after submission
            questionCreatorSection.style.display = 'none';
            quizReviewSection.style.display = 'block';

        } else {
            alert("Please fill in all required fields to publish the quiz.");
        }
    });

    editQuizButton.addEventListener('click', function() {
        quizReviewSection.style.display = 'none';
        questionCreatorSection.style.display = 'block';
    });


    updatePublishButtonState();
    quizTitleInput.addEventListener('input', updatePublishButtonState);

});