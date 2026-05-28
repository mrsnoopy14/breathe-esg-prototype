from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import LoginSerializer, UserSerializer


class LoginView(APIView):
    """
    POST /api/auth/login/

    Accepts username + password, returns a DRF auth token and the user object.
    This view is intentionally open (AllowAny) — credentials are the gate.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']
        token, _created = Token.objects.get_or_create(user=user)

        return Response(
            {
                'token': token.key,
                'user': UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """
    DELETE /api/auth/logout/

    Deletes the user's auth token, effectively invalidating the session.
    The client must discard the token on their side as well.
    """

    permission_classes = [IsAuthenticated]

    def delete(self, request):
        # delete() on a queryset is safer than .get() then .delete() — avoids
        # a DoesNotExist exception if the token was already removed.
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """
    GET /api/auth/me/

    Returns the profile of the currently authenticated user,
    including their company and role.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
