from rest_framework import serializers

class LLMConfigRequestSerializer(serializers.Serializer):
    llm_provider = serializers.ChoiceField(choices=["openai", "groq", "google"])
    model_name   = serializers.CharField()

class QuestionRequestSerializer(serializers.Serializer):
    question      = serializers.CharField()
    llm_provider  = serializers.ChoiceField(choices=["openai", "groq", "google"], required=False)
    model_name    = serializers.ChoiceField(required=False)

class QuestionResponseSerializer(serializers.Serializer):
    answer   = serializers.CharField()
    status   = serializers.CharField()
    llm_used = serializers.CharField()
