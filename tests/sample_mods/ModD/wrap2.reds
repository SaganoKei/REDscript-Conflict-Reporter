// ModD wrap of PlayerPuppet.OnUpdate to demonstrate wrap coexistence
@wrapMethod(PlayerPuppet)
func OnUpdate(delta: Float) -> Void {
    // Pre logic D
    wrappedMethod(delta);
    // Post logic D
}
