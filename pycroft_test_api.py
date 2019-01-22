# -*- coding: utf-8 -*-
from flask import Flask, jsonify

app = Flask('pycroft')


@app.route('/user/authenticate', methods=['POST'])
def authenticate():
    return jsonify(id=10564)


@app.route('/user/<int:user_id>')
def get_user(user_id: int):
    return jsonify(
        id=10564,
        user_id="10564-foo",
        login="lukasjuhrich",
        realname="Lukas Juhrich",
        status={
            'account_balanced': True,
            'network_access': True,
            'traffic_exceeded': False,
            'member': True,
            'violation': False,
        },
        room="Keller",
        mail="foo@bar.baz",
        cache=True,
        traffic_balance=1024**3,
        traffic_history=[],
        interfaces=[],
        finance_balance=30,
        finance_history=[],
        # TODO implement `cls.Meta.custom_constructors`, use `parse_date` for this
        last_finance_update="2018-01-01",
    )


@app.route('/user/from-ip')
def user_from_ip():
    return get_user(10564)


if __name__ == '__main__':
    app.run(debug=True, port=5050)
