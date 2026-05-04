from flask import Blueprint, request

index_bp = Blueprint("index", __name__)



@index_bp.route("/", methods = ["GET"])
def index():
    

    return "Hello world"