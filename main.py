from app import app, socketio

if __name__ == '__main__':
    # Initialize blockchain if needed
    from blockchain import BlockchainSimulator
    with app.app_context():
        BlockchainSimulator.initialize_genesis_block()
    
    # Start the application with SocketIO
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False, log_output=False)
